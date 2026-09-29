#!/usr/bin/env python3
"""Query the regulation RAG index from the command line.

    python scripts/search_regulation.py "suelo de LGD para hipotecas"
    python scripts/search_regulation.py "definición de default" -k 8

Build the index first with ``scripts/build_regulation_embeddings.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.embeddings import get_embedding_service  # noqa: E402
from src.knowledge.regulation_vector_store import (  # noqa: E402
    DEFAULT_INDEX_PATH, RegulationVectorStore,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    args = ap.parse_args()

    if not args.index.is_file():
        sys.exit(f"No index at {args.index} — run scripts/build_regulation_embeddings.py first.")
    store = RegulationVectorStore.load(args.index)
    embedder = get_embedding_service()
    built_with = store.manifest.get("embedding_backend")
    if embedder.resolved_backend != built_with:
        print(f"WARNING: index built with {built_with!r}, "
              f"querying with {embedder.resolved_backend!r} — rebuild the index.", file=sys.stderr)

    for hit in store.search_text(args.query, embedder, k=args.k):
        print(f"[{hit.score:.3f}] {hit.citation} — {hit.section}")
        print(f"    {hit.text[:300]}\n")


if __name__ == "__main__":
    main()
