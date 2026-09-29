#!/usr/bin/env python3
"""Ingest a guidelines PDF into the paragraph JSON the RAG chunker consumes.

Output records follow ``src/knowledge/regulation_chunker.py``'s input format::

    {"id": "par_14", "paragraph": 14,
     "section": "4.2 Requisitos de los datos",
     "subsection": "4.2.1 Calidad de los datos",
     "text": "..."}

Heuristics (tuned for EBA guideline layout, where paragraphs are numbered
``N.`` and headings are numbered ``4``, ``4.2``, ``4.2.1`` without a trailing
dot):

- lines repeated on most pages (running headers/footers) and bare page
  numbers are dropped;
- a paragraph starts at ``N.`` only when ``N`` is the next expected number —
  this rejects numbered lists and stray numbers inside paragraphs;
- a heading line that wraps is joined with its continuation lines up to the
  next paragraph start;
- end-of-line hyphenation (``calibra-`` / ``ción``) is undone.

Check the output: PDF text extraction is lossy, and every document needs a
look at the first/last paragraphs and the section list before indexing.

    python scripts/ingest_pdf.py guidelines.pdf
    python scripts/ingest_pdf.py guidelines.pdf --out data/regulation/eba_gl_2017_16_articles.json
    python scripts/ingest_pdf.py guidelines.pdf --start-page 12
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_PARA = re.compile(r"^(\d{1,3})\.\s+(\S.*)$")
_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\s+([A-ZÁÉÍÓÚÑ].{1,150})$")
_PAGE_NUM = re.compile(r"^\s*(?:p[áa]g(?:ina)?\.?\s*)?\d{1,4}(?:\s*/\s*\d{1,4})?\s*$", re.I)


def extract_pages(pdf_path: Path) -> list[list[str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return [
        [ln.strip() for ln in (page.extract_text() or "").splitlines() if ln.strip()]
        for page in reader.pages
    ]


def strip_running_lines(pages: list[list[str]], min_ratio: float = 0.5) -> list[str]:
    """Drop headers/footers (lines on >= min_ratio of pages) and page numbers."""
    counts = Counter(ln for page in pages for ln in set(page))
    threshold = max(2, int(len(pages) * min_ratio))
    running = {ln for ln, n in counts.items() if n >= threshold}
    return [
        ln for page in pages for ln in page
        if ln not in running and not _PAGE_NUM.match(ln)
    ]


def _join(lines: list[str]) -> str:
    text = ""
    for ln in lines:
        if text.endswith("-") and ln[:1].islower():
            text = text[:-1] + ln
        else:
            text = f"{text} {ln}" if text else ln
    return re.sub(r"\s+", " ", text).strip()


def parse_paragraphs(lines: list[str], first_paragraph: int = 1) -> list[dict]:
    records: list[dict] = []
    section = subsection = ""
    expected = first_paragraph
    current: dict | None = None
    body: list[str] = []
    heading: list[str] | None = None   # heading being assembled (may wrap)
    heading_depth = 0

    def flush_heading() -> None:
        nonlocal heading, section, subsection
        if heading is None:
            return
        title = _join(heading)
        if heading_depth <= 2:
            section, subsection = title, ""
        else:
            subsection = title
        heading = None

    def flush_paragraph() -> None:
        nonlocal current, body
        if current is not None:
            current["text"] = _join(body)
            records.append(current)
        current, body = None, []

    for ln in lines:
        m_par = _PARA.match(ln)
        if m_par and int(m_par.group(1)) == expected:
            flush_heading()
            flush_paragraph()
            current = {
                "id": f"par_{expected}", "paragraph": expected,
                "section": section, "subsection": subsection,
            }
            body = [m_par.group(2)]
            expected += 1
            continue
        m_head = _HEADING.match(ln)
        if m_head and not ln.endswith("."):
            flush_heading()
            flush_paragraph()
            heading = [ln]
            heading_depth = m_head.group(1).count(".") + 1
            continue
        if heading is not None and len(_join(heading)) + len(ln) < 200:
            heading.append(ln)
        elif current is not None:
            body.append(ln)
        # text before the first paragraph (cover, TOC) is ignored

    flush_heading()
    flush_paragraph()
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="output JSON (default: data/regulation/<pdf stem>.json)")
    ap.add_argument("--start-page", type=int, default=1,
                    help="1-based page where the guideline text starts (skips cover/TOC)")
    ap.add_argument("--first-paragraph", type=int, default=1)
    args = ap.parse_args()

    pages = extract_pages(args.pdf)[args.start_page - 1:]
    records = parse_paragraphs(strip_running_lines(pages), args.first_paragraph)
    if not records:
        sys.exit("No numbered paragraphs found — check --start-page / --first-paragraph.")

    out = args.out or Path(__file__).resolve().parent.parent / "data" / "regulation" / f"{args.pdf.stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    sections = sorted({r["section"] for r in records if r["section"]})
    print(f"{len(records)} paragraphs (§{records[0]['paragraph']}–§{records[-1]['paragraph']}), "
          f"{len(sections)} sections → {out}")
    empty = [r["paragraph"] for r in records if not r["text"]]
    if empty:
        print(f"WARNING: empty paragraphs: {empty}", file=sys.stderr)


if __name__ == "__main__":
    main()
