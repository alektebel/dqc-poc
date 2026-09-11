"""Context attribution for generated DQCs — which inputs produced this output?

Two complementary mechanisms, because they answer different questions and cost
wildly different amounts:

**Structural attribution** (:func:`attribute_sql_structurally`) — free, exact,
always on. Generated DQCs are SQL, and SQL *names* what it reads. Parsing the
identifiers out of the query and matching them against the dictionary fields
that were in the prompt tells you, with certainty, which fields the query
actually used — and, through each field's ``reg_ref``, which PD/LGD guideline
paragraph stands behind it. No model calls.

**Counterfactual attribution** (:func:`attribute_by_ablation`) — expensive,
run on demand. Structural attribution cannot explain a field that shaped the
query without being named in it: a description that fixed a threshold, a
formula that determined a join, a guideline paragraph that motivated the rule.
For those, remove one context unit, regenerate, and measure how far the output
moved. A unit whose removal changes the query is one the query depended on.

This is ContextCite's mechanism (Cohen-Wang et al., 2024) with a deliberate
substitution. ContextCite fits a surrogate on the *log-probability* of the
response under randomly ablated context subsets. The Bedrock Runtime API
exposes no logprobs — ``ConverseResponse`` carries only output, stopReason,
usage, metrics and trace, and ``InferenceConfiguration`` only maxTokens,
temperature, topP and stopSequences — so that signal is unavailable against
Nova. Instead we ablate one *meaningful* unit at a time (a field, a guideline
paragraph) and score by output distance.

The trade is deliberate: leave-one-out over n units costs n calls instead of
the 32-64 random subsets ContextCite samples, it needs no surrogate model, and
the result is a direct counterfactual ("the SQL changes when this field is
removed") rather than a regression coefficient. What it gives up is
interaction effects — two fields that are individually redundant but jointly
necessary both score ~0. :func:`attribute_by_ablation` reports those as
``suspected_redundancy`` so they are visible rather than silently missed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Callable, Iterable, Sequence

__all__ = [
    "ContextUnit",
    "Attribution",
    "AttributionReport",
    "units_from_fields",
    "units_from_reg_chunks",
    "sql_identifiers",
    "attribute_sql_structurally",
    "attribute_by_ablation",
    "sql_similarity",
]

# SQL identifiers: letters/digits/underscore, optionally qualified (t.COL).
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*")
_STRING_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_COMMENT_RE = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)

# Reserved words are not evidence of anything; excluding them keeps the
# identifier set to things the dictionary could plausibly have supplied.
_SQL_KEYWORDS = frozenset("""
select from where group by having order asc desc limit offset union all distinct
join inner left right full outer on as and or not in is null like between exists
case when then else end count sum avg min max cast convert coalesce nullif
create table view insert update delete set values into with recursive
abs round floor ceil trunc length substr substring trim upper lower
date year month day datepart datediff current_date current_timestamp
true false unknown intersect except over partition row_number rank dense_rank
""".split())


@dataclass(frozen=True)
class ContextUnit:
    """One removable piece of prompt context.

    ``kind`` is "field" or "regulation"; ``key`` identifies it (a column name,
    a chunk id); ``citation`` is the regulatory reference to show a reviewer,
    when there is one.
    """

    kind: str
    key: str
    label: str = ""
    text: str = ""
    citation: str = ""

    def display(self) -> str:
        return f"{self.label or self.key}" + (f" ({self.citation})" if self.citation else "")


@dataclass
class Attribution:
    unit: ContextUnit
    score: float                 # 0..1, higher = the output depended on it more
    method: str                  # "structural" | "ablation"
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.unit.kind,
            "key": self.unit.key,
            "label": self.unit.label,
            "citation": self.unit.citation,
            "score": round(self.score, 4),
            "method": self.method,
            "evidence": self.evidence,
        }


@dataclass
class AttributionReport:
    attributions: list[Attribution] = dc_field(default_factory=list)
    baseline: str = ""
    calls: int = 0
    suspected_redundancy: list[str] = dc_field(default_factory=list)

    def used(self, threshold: float = 0.0) -> list[Attribution]:
        return [a for a in self.attributions if a.score > threshold]

    def citations(self, threshold: float = 0.0) -> list[str]:
        """Distinct regulatory citations behind the attributed context."""
        seen: list[str] = []
        for a in self.attributions:
            if a.score > threshold and a.unit.citation and a.unit.citation not in seen:
                seen.append(a.unit.citation)
        return seen

    def to_dict(self) -> dict:
        return {
            "attributions": [a.to_dict() for a in self.attributions],
            "citations": self.citations(),
            "calls": self.calls,
            "suspected_redundancy": self.suspected_redundancy,
        }


# ── building units ────────────────────────────────────────────────────────

def units_from_fields(fields: Iterable) -> list[ContextUnit]:
    """Dictionary entries as context units. Carries each field's ``reg_ref``
    through as the citation, so attributing a query to a field also attributes
    it to the PD/LGD paragraph that field is governed by."""
    units: list[ContextUnit] = []
    for f in fields:
        text = " ".join(str(x) for x in (
            getattr(f, "name", ""), getattr(f, "description", ""),
            getattr(f, "formula", "")) if x)
        units.append(ContextUnit(
            kind="field",
            key=str(getattr(f, "name", "")),
            label=str(getattr(f, "name", "")),
            text=text,
            citation=str(getattr(f, "reg_ref", "") or ""),
        ))
    return units


def units_from_reg_chunks(chunks: Iterable) -> list[ContextUnit]:
    """EBA GL/2017/16 chunks as context units (RegChunk or RegSearchHit)."""
    units: list[ContextUnit] = []
    for c in chunks:
        inner = getattr(c, "chunk", c)
        cid = getattr(inner, "chunk_id", None) or getattr(c, "chunk_id", "")
        cite = inner.citation() if hasattr(inner, "citation") else ""
        units.append(ContextUnit(
            kind="regulation",
            key=str(cid),
            label=f"§{getattr(inner, 'paragraph', '?')}",
            text=str(getattr(inner, "text", "")),
            citation=cite,
        ))
    return units


# ── structural attribution ────────────────────────────────────────────────

def sql_identifiers(sql: str) -> set[str]:
    """Upper-cased identifiers in a query, minus reserved words and the
    contents of string literals and comments."""
    if not sql:
        return set()
    cleaned = _COMMENT_RE.sub(" ", sql)
    cleaned = _STRING_RE.sub(" ", cleaned)
    out: set[str] = set()
    for match in _IDENT_RE.finditer(cleaned):
        for part in match.group(0).split("."):
            low = part.lower()
            if low and low not in _SQL_KEYWORDS and not low.isdigit():
                out.add(part.upper())
    return out


def attribute_sql_structurally(sql: str, units: Sequence[ContextUnit]) -> AttributionReport:
    """Which context units the query demonstrably reads. Exact and free.

    A field scores 1.0 when its column name appears in the query. Everything
    else scores 0.0 here — absence is not evidence of irrelevance, only of not
    being named, which is what :func:`attribute_by_ablation` is for.
    """
    idents = sql_identifiers(sql)
    report = AttributionReport(baseline=sql, calls=0)
    for unit in units:
        hit = unit.kind == "field" and unit.key.upper() in idents
        report.attributions.append(Attribution(
            unit=unit,
            score=1.0 if hit else 0.0,
            method="structural",
            evidence="named in the query" if hit else "",
        ))
    report.attributions.sort(key=lambda a: -a.score)
    return report


# ── counterfactual attribution ────────────────────────────────────────────

def sql_similarity(a: str, b: str) -> float:
    """Jaccard similarity over identifier sets, so formatting, aliasing and
    comment churn do not register as a semantic change."""
    ia, ib = sql_identifiers(a), sql_identifiers(b)
    if not ia and not ib:
        return 1.0
    if not ia or not ib:
        return 0.0
    return len(ia & ib) / len(ia | ib)


def attribute_by_ablation(
    units: Sequence[ContextUnit],
    generate: Callable[[Sequence[ContextUnit]], str],
    *,
    baseline: str | None = None,
    similarity: Callable[[str, str], float] = sql_similarity,
    max_units: int | None = None,
) -> AttributionReport:
    """Leave-one-out counterfactual attribution.

    ``generate`` is called once with every unit to establish the baseline
    (unless ``baseline`` is supplied), then once per unit with that unit
    removed. The attribution score is ``1 - similarity(baseline, ablated)``:
    removing an irrelevant unit changes nothing and scores 0.

    Costs ``len(units)`` calls (+1 without a baseline). Cap it with
    ``max_units`` when the dictionary is large; units are ablated in the order
    given, so pass them most-promising-first (for example the structural hits
    followed by the retriever's ranking).
    """
    report = AttributionReport()
    if baseline is None:
        baseline = generate(units)
        report.calls += 1
    report.baseline = baseline

    considered = list(units)[: max_units] if max_units else list(units)
    for unit in considered:
        remaining = [u for u in units if u.key != unit.key or u.kind != unit.kind]
        ablated = generate(remaining)
        report.calls += 1
        score = 1.0 - similarity(baseline, ablated)
        report.attributions.append(Attribution(
            unit=unit,
            score=max(0.0, min(1.0, score)),
            method="ablation",
            evidence="output unchanged without it" if score <= 0
                     else f"output diverged (similarity {1 - score:.2f})",
        ))

    # Leave-one-out is blind to interactions: two units that each cover for
    # the other both score 0 even though one is required. Flag the case where
    # the query names a unit that ablating it did not disturb.
    named = sql_identifiers(baseline)
    for a in report.attributions:
        if a.score <= 0.0 and a.unit.kind == "field" and a.unit.key.upper() in named:
            report.suspected_redundancy.append(a.unit.key)

    report.attributions.sort(key=lambda a: -a.score)
    return report
