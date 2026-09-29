"""PDF → paragraph JSON ingestion (scripts/ingest_pdf.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "ingest_pdf", Path(__file__).resolve().parents[1] / "scripts" / "ingest_pdf.py"
)
ingest_pdf = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest_pdf)


def test_parse_numbering_headings_and_hyphenation():
    lines = [
        "Índice",                       # before first paragraph: ignored
        "4 Requisitos generales de estimación de",
        "los parámetros de riesgo",     # wrapped heading continuation
        "1. Las entidades aplicarán la misma calibra-",
        "ción a todas las carteras.",
        "4.2.1 Calidad de los datos",
        "2. Las entidades evaluarán:",
        "3. condiciones en las que",    # next expected number → §3
        "a) la exhaustividad;",
        "5. estray number",             # out-of-sequence: stays in §3's body
        "4. Último párrafo.",
    ]
    recs = ingest_pdf.parse_paragraphs(lines)
    assert [r["paragraph"] for r in recs] == [1, 2, 3, 4]
    assert recs[0]["section"] == "4 Requisitos generales de estimación de los parámetros de riesgo"
    assert recs[0]["text"] == "Las entidades aplicarán la misma calibración a todas las carteras."
    assert recs[1]["subsection"] == "4.2.1 Calidad de los datos"
    assert "5. estray number" in recs[2]["text"]


def test_strip_running_lines_drops_headers_and_page_numbers():
    pages = [["EBA/GL/2017/16", "1. texto", "3"], ["EBA/GL/2017/16", "más texto", "4"]]
    assert ingest_pdf.strip_running_lines(pages) == ["1. texto", "más texto"]


def test_end_to_end_pdf(tmp_path):
    canvas_mod = pytest.importorskip("reportlab.pdfgen.canvas")
    pytest.importorskip("pypdf")
    pdf = tmp_path / "gl.pdf"
    c = canvas_mod.Canvas(str(pdf))
    for page_lines in (
        ["EBA/GL/2017/16", "5.3 Calibración de la PD", "1. La PD se calibrará", "a la tasa media a largo plazo.", "1"],
        ["EBA/GL/2017/16", "2. El margen de cautela se aplicará.", "2"],
    ):
        y = 800
        for ln in page_lines:
            c.drawString(50, y, ln)
            y -= 20
        c.showPage()
    c.save()
    recs = ingest_pdf.parse_paragraphs(ingest_pdf.strip_running_lines(ingest_pdf.extract_pages(pdf)))
    assert [(r["paragraph"], r["section"]) for r in recs] == [
        (1, "5.3 Calibración de la PD"), (2, "5.3 Calibración de la PD"),
    ]
    assert recs[0]["text"] == "La PD se calibrará a la tasa media a largo plazo."
