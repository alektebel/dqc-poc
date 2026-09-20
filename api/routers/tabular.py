"""One tabular reader for both uploads the app takes: .xlsx and .csv.

The dictionary parser and the cases loader used to call ``openpyxl``
directly, which made a CSV upload a 400. Both now go through
:func:`read_sheets`, which decides by the file's magic bytes rather than
its name (an .xlsx is a zip: ``PK\\x03\\x04``), so callers keep their
signatures and a mislabelled upload still reads correctly.

A CSV has no sheets, so it comes back as a single sheet named after the
convention the rest of the code already understands — a sheet name that
is simply not in the workbook falls back to "the first one".
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

__all__ = ["is_xlsx", "read_sheets", "first_sheet", "CSV_SHEET"]

CSV_SHEET = "CSV"

# Delimiters worth sniffing: Excel in a Spanish locale exports ';'.
_DELIMITERS = ",;\t|"
_SNIFF_BYTES = 8192


def is_xlsx(data: bytes) -> bool:
    """True when the payload is an OOXML workbook (a zip container)."""
    return data[:4] == b"PK\x03\x04"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _sniff_delimiter(text: str) -> str:
    sample = text[:_SNIFF_BYTES]
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        # Sniffer gives up on single-column files; count instead.
        head = sample.splitlines()[0] if sample.splitlines() else ""
        counts = {d: head.count(d) for d in _DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] else ","


# A CSV cell is text; an .xlsx cell is typed. Without this the two
# uploads do NOT behave the same: the generated controls run on SQLite,
# where every integer sorts before every string, so `EDAD > 130` matches
# EVERY row of a CSV — a control that silently reports the whole table.
_INT_RE = re.compile(r"^[+-]?(0|[1-9]\d*)$")
_DEC_RE = re.compile(r"^[+-]?(0|[1-9]\d*)\.\d+$")
_DEC_COMMA_RE = re.compile(r"^[+-]?(0|[1-9]\d*),\d+$")


def _coerce_cell(text: str, decimal_comma: bool) -> Any:
    """Numbers become numbers; everything else stays text.

    Leading zeros keep a value textual on purpose — an account number
    ``007`` is an identifier, not the integer 7.
    """
    if text == "":
        return None
    if _INT_RE.match(text):
        return int(text)
    if _DEC_RE.match(text):
        return float(text)
    if decimal_comma and _DEC_COMMA_RE.match(text):
        return float(text.replace(",", "."))
    return text


def _csv_rows(data: bytes) -> list[tuple]:
    text = _decode(data)
    delimiter = _sniff_delimiter(text)
    # "1,5" can only be a decimal number when the comma is not separating
    # the columns — which is exactly the Spanish Excel export.
    decimal_comma = delimiter != ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    return [tuple(_coerce_cell(cell.strip(), decimal_comma) for cell in row)
            for row in reader]


def read_sheets(data: bytes, filename: str | None = None
                ) -> list[tuple[str, list[tuple[Any, ...]]]]:
    """``[(sheet_name, rows)]`` for every sheet, rows as value tuples.

    A zip container is always read as a workbook, whatever it is called.
    Anything else named .xlsx/.xls is a corrupt or legacy file, NOT a CSV
    to be parsed leniently — reading it as text would turn a broken
    upload into a one-column dictionary of mojibake. Same for a payload
    carrying NUL bytes: it is binary, not a CSV.

    Rows are materialised rather than streamed: the workbook must be
    closed before returning, and every caller walks all of them anyway
    (the cases loader copies them into SQLite, the inspector counts
    them). Blank rows are kept — callers already skip them, and dropping
    them here would shift header detection on files that open with one.
    """
    if not is_xlsx(data):
        name = (filename or "").lower()
        if name.endswith((".xlsx", ".xls")):
            raise ValueError("no es un libro de Excel válido")
        if b"\x00" in data[:_SNIFF_BYTES]:
            raise ValueError("el fichero es binario, no un CSV")
        return [(CSV_SHEET, _csv_rows(data))]

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                data_only=True)
    try:
        return [(ws.title, list(ws.iter_rows(values_only=True)))
                for ws in wb.worksheets]
    finally:
        wb.close()


def first_sheet(data: bytes, sheet: str | None = None,
                filename: str | None = None
                ) -> tuple[str, list[tuple[Any, ...]]]:
    """The named sheet's rows, or the first sheet's when it is absent."""
    sheets = read_sheets(data, filename)
    if not sheets:
        return "", []
    for name, rows in sheets:
        if sheet and name == sheet:
            return name, rows
    return sheets[0]
