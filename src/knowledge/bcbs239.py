"""BCBS 239 — Principles for effective risk data aggregation and risk reporting.

The Basel Committee's BCBS 239 (July 2013) defines 14 principles split into
two halves:

  * Principles 1–6   — governance and risk-data-aggregation capabilities.
  * Principles 7–13  — risk-reporting practices.
  * Principle 14     — supervisory review.

This module is the single source of truth for the principle list so the DQC
generator can classify every control against BCBS 239, and so the Studio can
render and filter by principle. The code used throughout the codebase is the
``P<n>`` short form (e.g. ``P3``), matching the existing ``BCBS 239 P3``
convention in the eval harness.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principle:
    code: str          # "P3"
    name: str          # "Accuracy and integrity"
    scope: str         # "aggregation" | "reporting" | "supervisory"


PRINCIPLES: list[Principle] = [
    Principle("P1", "Governance", "aggregation"),
    Principle("P2", "Data architecture and IT infrastructure", "aggregation"),
    Principle("P3", "Accuracy and integrity", "aggregation"),
    Principle("P4", "Completeness", "aggregation"),
    Principle("P5", "Timeliness", "aggregation"),
    Principle("P6", "Adaptability", "aggregation"),
    Principle("P7", "Accuracy", "reporting"),
    Principle("P8", "Comprehensiveness", "reporting"),
    Principle("P9", "Clarity and usefulness", "reporting"),
    Principle("P10", "Frequency", "reporting"),
    Principle("P11", "Distribution", "reporting"),
    Principle("P12", "Review", "reporting"),
    Principle("P13", "Reconciliation", "reporting"),
    Principle("P14", "Supervisory review", "supervisory"),
]

PRINCIPLES_BY_CODE: dict[str, Principle] = {p.code: p for p in PRINCIPLES}

# DQC-type → most relevant BCBS 239 principle. Used as a deterministic
# fallback when the generation agent fails to classify (or runs in stub mode),
# so every control still carries a BCBS 239 label.
_TYPE_TO_CODE: dict[str, str] = {
    "completitud": "P4",     # Completeness
    "rango": "P3",           # Accuracy and integrity
    "formula": "P7",         # Accuracy
    "consistencia": "P13",   # Reconciliation
    "referencial": "P6",     # Adaptability (referential integrity across sources)
    "cross_field": "P13",    # Reconciliation
    "cross_table": "P13",    # Reconciliation
    "cardinality": "P6",     # Adaptability
}


def display(code: str) -> str:
    """Human-readable label for a principle code, e.g. ``P3 — Accuracy and
    integrity``. Returns the code itself (normalised) when unknown."""
    code = (code or "").strip().upper()
    if not code:
        return ""
    # Accept bare "P3" as well as longer forms like "BCBS 239 P3".
    if code.startswith("P") and code[1:].isdigit():
        p = PRINCIPLES_BY_CODE.get(code)
    else:
        p = None
    if p:
        return f"{p.code} — {p.name}"
    return code


def label(code: str) -> str:
    """Short label (``P3 — Accuracy and integrity``) for display in badges."""
    return display(code)


def normalise(code: str) -> str:
    """Coerce a user/LLM-supplied reference into a canonical ``P<n>`` code.

    Accepts ``P3``, ``BCBS 239 P3``, ``Principle 3``, ``principles for
    effective risk data aggregation ... (3)``, and the numeric ``3``.
    """
    text = (code or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if upper in PRINCIPLES_BY_CODE:
        return upper
    # "BCBS 239 P3" / "BCBS239 P3" / "P3"
    m = __import__("re").search(r"\bP\s*(\d{1,2})\b", upper)
    if m:
        code_str = f"P{int(m.group(1))}"
        return code_str if code_str in PRINCIPLES_BY_CODE else ""
    m = __import__("re").search(r"\b(\d{1,2})\b", upper)
    if m:
        code_str = f"P{int(m.group(1))}"
        return code_str if code_str in PRINCIPLES_BY_CODE else ""
    return ""


def default_for_type(tipo: str) -> str:
    """Deterministic fallback BCBS 239 code for a DQC ``tipo``."""
    return _TYPE_TO_CODE.get((tipo or "").strip().lower(), "P3")


def describe_principles() -> str:
    """Compact prompt-format listing of the 14 principles (code + name)."""
    return "\n".join(f"- {p.code}: {p.name} ({p.scope})" for p in PRINCIPLES)


__all__ = [
    "Principle", "PRINCIPLES", "PRINCIPLES_BY_CODE", "display", "label",
    "normalise", "default_for_type", "describe_principles",
]
