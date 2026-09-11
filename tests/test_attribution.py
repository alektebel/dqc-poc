"""Context attribution: structural (free, exact) and ablation (counterfactual)."""

from dataclasses import dataclass

import pytest

from src.knowledge.attribution import (
    ContextUnit, attribute_by_ablation, attribute_sql_structurally,
    sql_identifiers, sql_similarity, units_from_fields, units_from_reg_chunks,
)


@dataclass
class _Field:
    name: str
    description: str = ""
    formula: str = ""
    reg_ref: str = ""


@dataclass
class _Chunk:
    chunk_id: str
    paragraph: int
    text: str

    def citation(self) -> str:
        return f"EBA GL/2017/16 §{self.paragraph}"


# ── identifier extraction ────────────────────────────────────────────────

def test_identifiers_exclude_keywords_strings_and_comments():
    sql = ("SELECT ID, PD_ESTIMADA FROM t WHERE PD_ESTIMADA < 0 "
           "AND SEGMENTO = 'RETAIL' -- PD_REAL is not read here\n"
           "/* LGD_FINAL neither */")
    idents = sql_identifiers(sql)
    assert {"ID", "PD_ESTIMADA", "SEGMENTO"} <= idents
    assert "SELECT" not in idents and "WHERE" not in idents   # keywords
    assert "RETAIL" not in idents                              # string literal
    assert "PD_REAL" not in idents                             # line comment
    assert "LGD_FINAL" not in idents                           # block comment


def test_identifiers_split_qualified_names():
    assert {"CC", "PD_ESTIMADA"} <= sql_identifiers("SELECT cc.PD_ESTIMADA FROM x cc")


def test_identifiers_on_empty_sql():
    assert sql_identifiers("") == set()


# ── structural attribution ───────────────────────────────────────────────

def test_structural_attributes_only_named_fields():
    units = units_from_fields([
        _Field("PD_ESTIMADA", reg_ref="EBA GL/2017/16 §73"),
        _Field("LGD_FINAL", reg_ref="EBA GL/2017/16 §128"),
    ])
    report = attribute_sql_structurally(
        "SELECT * FROM t WHERE PD_ESTIMADA < 0", units)
    scored = {a.unit.key: a.score for a in report.attributions}
    assert scored["PD_ESTIMADA"] == 1.0
    assert scored["LGD_FINAL"] == 0.0
    assert report.calls == 0          # structural attribution is free


def test_structural_carries_the_regulatory_citation():
    """Attributing a query to a field also attributes it to the PD/LGD
    paragraph that governs that field."""
    units = units_from_fields([
        _Field("PD_ESTIMADA", reg_ref="EBA GL/2017/16 §73"),
        _Field("LGD_FINAL", reg_ref="EBA GL/2017/16 §128"),
    ])
    report = attribute_sql_structurally(
        "SELECT * FROM t WHERE PD_ESTIMADA < 0", units)
    assert report.citations() == ["EBA GL/2017/16 §73"]


def test_structural_is_case_insensitive():
    units = units_from_fields([_Field("Pd_Estimada")])
    report = attribute_sql_structurally("select * from t where PD_ESTIMADA < 0", units)
    assert report.attributions[0].score == 1.0


def test_field_named_only_in_a_comment_is_not_attributed():
    units = units_from_fields([_Field("LGD_FINAL")])
    report = attribute_sql_structurally(
        "SELECT * FROM t WHERE PD < 0 -- LGD_FINAL unused", units)
    assert report.attributions[0].score == 0.0


# ── similarity ───────────────────────────────────────────────────────────

def test_similarity_ignores_formatting_and_aliases():
    a = "SELECT ID, PD_ESTIMADA FROM t WHERE PD_ESTIMADA < 0"
    b = "select  id ,\n  pd_estimada\nfrom t\nwhere pd_estimada < 0"
    assert sql_similarity(a, b) == 1.0


def test_similarity_drops_when_a_column_changes():
    a = "SELECT ID FROM t WHERE PD_ESTIMADA < 0"
    b = "SELECT ID FROM t WHERE LGD_FINAL < 0"
    assert 0.0 < sql_similarity(a, b) < 1.0


def test_similarity_of_two_empty_queries():
    assert sql_similarity("", "") == 1.0
    assert sql_similarity("SELECT A FROM t", "") == 0.0


# ── ablation attribution ─────────────────────────────────────────────────

def test_ablation_scores_the_field_the_output_depends_on():
    units = units_from_fields([_Field("PD_ESTIMADA"), _Field("IRRELEVANTE")])

    def generate(available):
        names = {u.key for u in available}
        # The generator can only use PD_ESTIMADA when it is present.
        if "PD_ESTIMADA" in names:
            return "SELECT ID FROM t WHERE PD_ESTIMADA < 0"
        return "SELECT ID FROM t"

    report = attribute_by_ablation(units, generate)
    scored = {a.unit.key: a.score for a in report.attributions}
    assert scored["PD_ESTIMADA"] > 0.0
    assert scored["IRRELEVANTE"] == 0.0
    assert report.calls == 3          # 1 baseline + 1 per unit


def test_ablation_accepts_a_supplied_baseline_and_saves_a_call():
    units = units_from_fields([_Field("A")])
    report = attribute_by_ablation(
        units, lambda avail: "SELECT 1 FROM t", baseline="SELECT 1 FROM t")
    assert report.calls == 1


def test_ablation_attributes_a_regulation_paragraph():
    """The rule itself can be traced to the guideline paragraph behind it."""
    units = units_from_reg_chunks([
        _Chunk("par_73#0", 73, "PD estimates shall not be negative"),
        _Chunk("par_99#0", 99, "unrelated text"),
    ])

    def generate(available):
        paras = {u.key for u in available}
        return ("SELECT ID FROM t WHERE PD_ESTIMADA < 0" if "par_73#0" in paras
                else "SELECT ID FROM t")

    report = attribute_by_ablation(units, generate)
    top = report.attributions[0]
    assert top.unit.key == "par_73#0"
    assert top.unit.citation == "EBA GL/2017/16 §73"
    assert report.citations() == ["EBA GL/2017/16 §73"]


def test_ablation_flags_interaction_blindness():
    """Leave-one-out cannot see two units that cover for each other. When the
    query names a field whose removal changed nothing, say so rather than
    reporting a confident zero."""
    units = units_from_fields([_Field("PD_ESTIMADA"), _Field("PD_REAL")])
    # A generator that always emits both names, whatever it is given.
    report = attribute_by_ablation(
        units, lambda avail: "SELECT PD_ESTIMADA, PD_REAL FROM t")
    assert set(report.suspected_redundancy) == {"PD_ESTIMADA", "PD_REAL"}


def test_ablation_max_units_caps_the_cost():
    units = units_from_fields([_Field(f"F{i}") for i in range(10)])
    report = attribute_by_ablation(
        units, lambda avail: "SELECT 1 FROM t", baseline="SELECT 1 FROM t",
        max_units=3)
    assert report.calls == 3
    assert len(report.attributions) == 3


def test_report_serialises_for_the_trace():
    units = units_from_fields([_Field("PD_ESTIMADA", reg_ref="EBA GL/2017/16 §73")])
    d = attribute_sql_structurally("SELECT PD_ESTIMADA FROM t", units).to_dict()
    assert d["attributions"][0]["citation"] == "EBA GL/2017/16 §73"
    assert d["citations"] == ["EBA GL/2017/16 §73"]
