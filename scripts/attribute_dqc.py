#!/usr/bin/env python
"""Counterfactual attribution for one DQC rule — what was the SQL based on?

Structural attribution (always on during generation) names the dictionary
fields the query *reads*. This answers the harder question: which context the
query *depended on*, including context it never names — a description that
fixed a threshold, a formula that determined a join, a PD/LGD paragraph that
motivated the rule at all.

Method: remove one context unit, regenerate, measure how far the SQL moved.
See ``src/knowledge/attribution.py`` for why this is leave-one-out over
meaningful units rather than ContextCite's logprob surrogate (the Bedrock
Runtime API returns no logprobs).

Cost: one model call per unit. Use --max-units to cap it.

    python scripts/attribute_dqc.py \\
        --rule "La PD estimada no puede ser negativa" \\
        --dictionary DQC/eval/data_dictionary.md --max-units 8

    # include the EBA GL/2017/16 paragraphs retrieved for the rule
    python scripts/attribute_dqc.py --rule "..." --dictionary ... --regulation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routers import dqc_react as react                      # noqa: E402
from api.routers.dqc_dictionary import FieldEntry               # noqa: E402
from src.knowledge import attribution as attrib, get_client     # noqa: E402


def load_fields(path: Path) -> list[FieldEntry]:
    """Field entries from a markdown dictionary table (| name | type | desc |)."""
    fields: list[FieldEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or not cells[0] or set(cells[0]) <= set("- :"):
            continue
        if cells[0].lower() in {"campo", "field", "name", "nombre"}:
            continue
        fields.append(FieldEntry(
            name=cells[0], type=cells[1] if len(cells) > 1 else "",
            description=cells[2] if len(cells) > 2 else "",
            reg_ref=cells[3] if len(cells) > 3 else ""))
    return fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rule", required=True, help="the DQC rule in natural language")
    ap.add_argument("--dictionary", required=True, type=Path,
                    help="markdown field dictionary")
    ap.add_argument("--table", default="mylib.ciclos_recuperacion")
    ap.add_argument("--max-units", type=int, default=10,
                    help="cap the ablation cost (one model call per unit)")
    ap.add_argument("--regulation", action="store_true",
                    help="also ablate the EBA GL/2017/16 paragraphs retrieved "
                         "for this rule (requires a built regulation index)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    fields = load_fields(args.dictionary)
    if not fields:
        print(f"No fields parsed from {args.dictionary}", file=sys.stderr)
        return 1
    client = get_client()

    def generate(available) -> str:
        keep = {u.key for u in available if u.kind == "field"}
        subset = [f for f in fields if f.name in keep]
        if not subset:
            return ""
        try:
            result = react.generate_sas(args.rule, subset, args.table, client)
            dqcs = result.get("dqcs") or []
            return dqcs[0].get("regla_sql", "") if dqcs else ""
        except Exception:  # noqa: BLE001 — an ablation that fails is a big change
            return ""

    units = attrib.units_from_fields(fields)

    if args.regulation:
        try:
            from src.knowledge.regulation_vector_store import get_default_store
            from src.knowledge.embeddings import get_embedder  # type: ignore
            store = get_default_store()
            if store is None:
                print("No regulation index found — run "
                      "scripts/build_regulation_embeddings.py first.",
                      file=sys.stderr)
            else:
                hits = store.search_text(args.rule, get_embedder(), k=5)
                units = units + attrib.units_from_reg_chunks(hits)
        except Exception as exc:  # noqa: BLE001
            print(f"Regulation units unavailable: {exc}", file=sys.stderr)

    baseline = generate(units)
    if not baseline:
        print("Baseline generation produced no SQL — cannot attribute.",
              file=sys.stderr)
        return 1

    # Ablate the named fields first: they are the likeliest to matter, so a
    # --max-units cap spends its budget where the signal is.
    named = attrib.sql_identifiers(baseline)
    units.sort(key=lambda u: (u.kind != "field", u.key.upper() not in named))

    report = attrib.attribute_by_ablation(
        units, generate, baseline=baseline, max_units=args.max_units)

    if args.json:
        print(json.dumps({"rule": args.rule, "baseline": baseline,
                          **report.to_dict()}, ensure_ascii=False, indent=2))
        return 0

    print(f"\nRULE      {args.rule}")
    print(f"BASELINE  {baseline}\n")
    print(f"{'score':>6}  {'kind':<11} unit")
    print("─" * 64)
    for a in report.attributions:
        bar = "█" * int(round(a.score * 20))
        print(f"{a.score:>6.2f}  {a.unit.kind:<11} {a.unit.display()}  {bar}")
    if report.citations():
        print("\nCitations behind the attributed context:")
        for c in report.citations():
            print(f"  - {c}")
    if report.suspected_redundancy:
        print("\n! Named in the query but ablating changed nothing — leave-one-out")
        print("  cannot separate mutually redundant context:")
        for k in report.suspected_redundancy:
            print(f"  - {k}")
    print(f"\n{report.calls} model call(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
