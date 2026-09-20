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


# ── surrogate (ContextCite) attribution ──────────────────────────────────

def test_fit_lasso_recovers_sparse_weights():
    """L1 must zero out a feature with no effect, not spread weight onto it."""
    from src.knowledge.attribution import fit_lasso
    X = [[1, 1, 1], [1, 0, 1], [0, 1, 0], [0, 0, 1],
         [1, 1, 0], [0, 1, 1], [1, 0, 0], [0, 0, 0]]
    y = [3.0 * r[0] - 2.0 * r[1] for r in X]
    w = fit_lasso([[float(v) for v in r] for r in X], y, alpha=0.001)
    assert w[0] == pytest.approx(3.0, abs=0.05)
    assert w[1] == pytest.approx(-2.0, abs=0.05)
    assert w[2] == 0.0


def test_fit_lasso_handles_empty_input():
    from src.knowledge.attribution import fit_lasso
    assert fit_lasso([], []) == []


def test_surrogate_attributes_the_supporting_unit():
    from src.knowledge.attribution import attribute_by_surrogate
    units = units_from_fields([_Field("PD_ESTIMADA"), _Field("RUIDO")])

    def logprob(subset):
        # The fixed response is only likely when PD_ESTIMADA is in context.
        return -1.0 if any(u.key == "PD_ESTIMADA" for u in subset) else -20.0

    report = attribute_by_surrogate(units, logprob, n_samples=24, seed=1)
    scored = {a.unit.key: a.score for a in report.attributions}
    assert scored["PD_ESTIMADA"] > 0.5
    assert abs(scored["RUIDO"]) < 0.2
    assert report.calls == 24          # cost is fixed by n_samples, not by unit count


def test_surrogate_cost_is_independent_of_context_size():
    """The reason to prefer it over leave-one-out on a large dictionary."""
    from src.knowledge.attribution import attribute_by_surrogate
    units = units_from_fields([_Field(f"F{i}") for i in range(73)])
    report = attribute_by_surrogate(units, lambda s: -1.0, n_samples=32, seed=0)
    assert report.calls == 32          # not 73
    assert len(report.attributions) == 73


def test_surrogate_reports_a_unit_that_argues_against_the_response():
    from src.knowledge.attribution import attribute_by_surrogate
    units = units_from_fields([_Field("APOYA"), _Field("CONTRADICE")])

    def logprob(subset):
        keys = {u.key for u in subset}
        return -5.0 + (4.0 if "APOYA" in keys else 0.0) - (4.0 if "CONTRADICE" in keys else 0.0)

    report = attribute_by_surrogate(units, logprob, n_samples=32, seed=3)
    scored = {a.unit.key: a.score for a in report.attributions}
    assert scored["APOYA"] > 0
    assert scored["CONTRADICE"] < 0


def test_surrogate_on_empty_units():
    from src.knowledge.attribution import attribute_by_surrogate
    report = attribute_by_surrogate([], lambda s: 0.0)
    assert report.attributions == [] and report.calls == 0


# ── claimed vs actual reconciliation (free grounding signal) ─────────────

def test_reconcile_confirms_a_truthful_claim():
    from src.knowledge.attribution import reconcile_claimed_fields
    r = reconcile_claimed_fields("SELECT ID FROM t WHERE PD_ESTIMADA < 0",
                                 ["PD_ESTIMADA"])
    assert r["confirmed"] == ["PD_ESTIMADA"]
    assert r["unsupported_claim"] == []
    assert r["claim_precision"] == 1.0   # everything it claimed, it used


def test_reconcile_catches_a_field_the_model_claimed_but_never_used():
    """The shape of a hallucinated justification: campos_entrada asserts a
    dependency the query does not act on."""
    from src.knowledge.attribution import reconcile_claimed_fields
    r = reconcile_claimed_fields("SELECT ID FROM t WHERE PD_ESTIMADA < 0",
                                 ["PD_ESTIMADA", "LGD_FINAL"])
    assert r["unsupported_claim"] == ["LGD_FINAL"]
    assert r["claim_precision"] == 0.5   # half its account was unsupported


def test_reconcile_reports_an_undeclared_read():
    from src.knowledge.attribution import reconcile_claimed_fields
    units = units_from_fields([_Field("PD_ESTIMADA"), _Field("SEGMENTO")])
    r = reconcile_claimed_fields(
        "SELECT ID FROM t WHERE PD_ESTIMADA < 0 AND SEGMENTO = 'X'",
        ["PD_ESTIMADA"], units)
    assert r["undeclared_use"] == ["SEGMENTO"]


def test_reconcile_ignores_aliases_when_units_are_supplied():
    """Table aliases and computed names are not undeclared field reads."""
    from src.knowledge.attribution import reconcile_claimed_fields
    units = units_from_fields([_Field("PD_ESTIMADA")])
    sql = "SELECT cc.PD_ESTIMADA AS PD_CALC FROM tabla cc"
    assert reconcile_claimed_fields(sql, ["PD_ESTIMADA"], units)["undeclared_use"] == []
    # without units, the alias and the computed name look like reads
    assert reconcile_claimed_fields(sql, ["PD_ESTIMADA"])["undeclared_use"]


def test_reconcile_is_case_insensitive_and_free():
    from src.knowledge.attribution import reconcile_claimed_fields
    r = reconcile_claimed_fields("select pd_estimada from t", ["PD_Estimada"])
    assert r["confirmed"] == ["PD_ESTIMADA"]


def test_precision_and_recall_answer_different_questions():
    """Claiming fields it never used is the hallucination signal; using fields
    it never claimed only means the account is incomplete."""
    from src.knowledge.attribution import reconcile_claimed_fields
    units = units_from_fields([_Field("A"), _Field("B"), _Field("C")])

    over = reconcile_claimed_fields("SELECT A FROM t", ["A", "B", "C"], units)
    assert over["claim_precision"] < 1.0 and over["claim_recall"] == 1.0

    under = reconcile_claimed_fields("SELECT A, B, C FROM t", ["A"], units)
    assert under["claim_precision"] == 1.0 and under["claim_recall"] < 1.0


def test_reconcile_with_nothing_claimed_reports_no_precision():
    from src.knowledge.attribution import reconcile_claimed_fields
    units = units_from_fields([_Field("A")])
    r = reconcile_claimed_fields("SELECT A FROM t", [], units)
    assert r["claim_precision"] is None     # no account to verify
    assert r["undeclared_use"] == ["A"]
