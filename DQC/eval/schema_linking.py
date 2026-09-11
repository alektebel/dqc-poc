#!/usr/bin/env python
"""Schema-linking recall — does the retriever keep the fields the answer needs?

``dqc_dictionary.select_relevant_fields`` is a tier-1 filter: it ranks the
dictionary against the rule and sends only the top slice to the generator. That
is the right design, but it creates a silent, unrecoverable failure. If a field
the correct SQL must reference is cut before generation, no prompt improvement,
retry or judge downstream can bring it back — and nothing in the harness
currently notices.

This measures it directly. For each golden trace, take the fields the gold
SQL references, run the retriever, and check they survived.

    python DQC/eval/schema_linking.py
    python DQC/eval/schema_linking.py --fail-under 1.0      # CI gate
    python DQC/eval/schema_linking.py --no-embedder         # lexical only

Recall should be 1.0. Anything less is a ceiling on every other metric, so
raise the cap or fix the scorer before touching generation prompts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.routers import dqc_dictionary as dict_ai            # noqa: E402
from api.routers.dqc_dictionary import FieldEntry            # noqa: E402
from src.knowledge.attribution import sql_identifiers        # noqa: E402

HERE = Path(__file__).resolve().parent


def load_dictionary_fields(path: Path) -> list[FieldEntry]:
    """Field entries from ``data_dictionary.md`` — the source of truth the
    coverage matrix already uses.

    Columns: Field | Type | Layer | Null | Description | Reg ref. The Reg ref
    is carried through so attribution can name the PD/LGD paragraph behind a
    field, not just the field.
    """
    fields: list[FieldEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = cells[0]
        if not name or set(name) <= set("- :") or name.lower() == "field":
            continue
        ref = cells[5] if len(cells) > 5 else ""
        fields.append(FieldEntry(
            name=name,
            type=cells[1],
            description=cells[4] if len(cells) > 4 else "",
            nullable=cells[3] if len(cells) > 3 else "",
            reg_ref="" if ref in {"—", "-", ""} else ref,
        ))
    return fields


def gold_fields_for(trace: dict, known: set[str]) -> set[str]:
    """Field names the trace's gold answer references.

    Taken from each gold DQC's ``regla_sql`` (parsed) and ``campos_entrada``
    (declared), intersected with the dictionary so aliases and literals in the
    query do not count as fields.
    """
    out: set[str] = set()
    for gold in trace.get("gold") or []:
        if gold.get("regla_sql"):
            out |= {i for i in sql_identifiers(str(gold["regla_sql"])) if i in known}
        for name in gold.get("campos_entrada") or []:
            if str(name).upper() in known:
                out.add(str(name).upper())
    if trace.get("variable") and str(trace["variable"]).upper() in known:
        out.add(str(trace["variable"]).upper())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", type=Path, default=HERE / "golden_traces.json")
    ap.add_argument("--dictionary", type=Path, default=HERE / "data_dictionary.md")
    ap.add_argument("--fail-under", type=float, default=None)
    ap.add_argument("--no-embedder", action="store_true",
                    help="lexical scoring only, to isolate the semantic channel")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    fields = load_dictionary_fields(args.dictionary)
    if not fields:
        print(f"No fields parsed from {args.dictionary}", file=sys.stderr)
        return 1
    known = {f.name.upper() for f in fields}

    raw = json.loads(args.traces.read_text(encoding="utf-8"))
    traces = raw if isinstance(raw, list) else raw.get("traces", [])

    embedder = None
    if not args.no_embedder:
        try:
            from api.routers.dqc_react import _field_embedder  # noqa: SLF001
            embedder = _field_embedder()          # the same call generation makes
        except Exception:  # noqa: BLE001
            embedder = None

    rows, total_gold, total_kept = [], 0, 0
    for trace in traces:
        rule = trace.get("request") or trace.get("rule") or ""
        gold = gold_fields_for(trace, known)
        if not rule or not gold:
            continue
        kept = {f.name.upper() for f in
                dict_ai.select_relevant_fields(fields, [rule], embedder=embedder)}
        missing = sorted(gold - kept)
        total_gold += len(gold)
        total_kept += len(gold & kept)
        rows.append({
            "id": trace.get("trace_id") or rule[:40],
            "recall": round(len(gold & kept) / len(gold), 3),
            "missing": missing,
        })

    if not rows:
        print("No golden trace carries both a request and gold SQL.",
              file=sys.stderr)
        return 1

    micro = total_kept / total_gold if total_gold else 1.0
    perfect = sum(1 for r in rows if r["recall"] == 1.0)

    if args.json:
        print(json.dumps({"micro_recall": round(micro, 4),
                          "traces_complete": perfect, "traces": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"\nSchema-linking recall  (embedder: "
              f"{'on' if embedder else 'off'})")
        print("─" * 62)
        for r in rows:
            flag = "" if r["recall"] == 1.0 else f"   MISSING {', '.join(r['missing'])}"
            print(f"  {r['recall']:>5.2f}  {str(r['id'])[:38]:<38}{flag}")
        print("─" * 62)
        print(f"  micro recall {micro:.3f}   complete traces {perfect}/{len(rows)}")
        if micro < 1.0:
            print("\n  A dropped field cannot be recovered downstream. Raise "
                  "MAX_FIELDS_PER_CALL\n  or fix the scorer before tuning "
                  "generation prompts.")

    if args.fail_under is not None and micro < args.fail_under:
        print(f"\nFAIL: {micro:.3f} < {args.fail_under}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
