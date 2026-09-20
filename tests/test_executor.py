"""Where a control runs, and what it is allowed to do there.

``DatabaseExecutor`` is exercised against sqlite3, which is a DB-API 2.0
driver like cx_Oracle or pyodbc: the same calls the bank's connection
would receive, without a bank.
"""

from __future__ import annotations

import sqlite3

import pytest

from api.dq.executor import (
    DatabaseExecutor,
    NotReadOnly,
    QueryExecutor,
    UploadedTableExecutor,
    assert_read_only,
)
from api.routers import dqc_react as react


@pytest.fixture()
def bank_db(tmp_path):
    """A table that already lives in a database — nothing was uploaded."""
    conn = sqlite3.connect(tmp_path / "core.db", check_same_thread=False)
    conn.execute("CREATE TABLE contratos ("
                 "ID_CONTRATO TEXT, EDAD_CLIENTE INTEGER, ESTADO TEXT)")
    conn.executemany("INSERT INTO contratos VALUES (?,?,?)", [
        ("CT-1", 140, "Activo"), ("CT-2", 44, "Activo"),
        ("CT-3", 135, "Cancelado"), ("CT-4", 61, "Activo")])
    conn.commit()
    return conn


# ── read-only enforcement ────────────────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130",
    "select * from contratos",
    "WITH malos AS (SELECT * FROM contratos WHERE EDAD_CLIENTE > 130) "
    "SELECT * FROM malos",
    "SELECT ID_CONTRATO FROM contratos WHERE ESTADO = 'deleted'",   # in a literal
    "SELECT ID_CONTRATO FROM contratos; ",                          # trailing ;
])
def test_a_plain_select_is_accepted(sql):
    assert_read_only(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM contratos",
    "UPDATE contratos SET EDAD_CLIENTE = 0",
    "DROP TABLE contratos",
    "SELECT * FROM contratos; DROP TABLE contratos",
    "SELECT * INTO otra FROM contratos",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "PRAGMA table_info(contratos)",
    "",
])
def test_anything_that_is_not_a_read_is_refused(sql):
    with pytest.raises(NotReadOnly):
        assert_read_only(sql)


def test_a_comment_cannot_smuggle_a_statement():
    with pytest.raises(NotReadOnly):
        assert_read_only("SELECT 1 -- harmless\n; DROP TABLE contratos")


# ── the database executor ────────────────────────────────────────────────────

def test_it_reads_the_shape_of_the_table(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos")
    assert ex.headers == ["ID_CONTRATO", "EDAD_CLIENTE", "ESTADO"]
    assert ex.n_rows == 4
    assert isinstance(ex, QueryExecutor)


def test_it_runs_a_control_where_the_data_is(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos")
    result = ex.run("SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130")
    assert result["ok"] is True
    assert result["n_casos"] == 2
    assert result["columnas"] == ["ID_CONTRATO"]
    assert {row["ID_CONTRATO"] for row in result["ejemplos"]} == {"CT-1", "CT-3"}


def test_it_rewrites_the_table_name_the_prompt_used(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos", prompt_table="mylib.contratos")
    result = ex.run("SELECT ID_CONTRATO FROM mylib.contratos "
                    "WHERE EDAD_CLIENTE > 130")
    assert result["ok"] is True, result.get("error")
    assert result["n_casos"] == 2


def test_a_broken_query_comes_back_as_an_error_not_an_exception(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos")
    result = ex.run("SELECT NO_EXISTE FROM contratos")
    assert result["ok"] is False
    assert "contratos" in result["error"]


def test_a_write_never_reaches_the_connection(bank_db):
    """The query was written by a model; the table is the bank's."""
    ex = DatabaseExecutor(bank_db, "contratos")
    result = ex.run("DELETE FROM contratos")
    assert result["ok"] is False
    assert "solo lectura" in result["error"] or "SELECT" in result["error"]
    # and the table is untouched
    assert bank_db.execute("SELECT COUNT(*) FROM contratos").fetchone()[0] == 4


def test_it_samples_real_values_for_grounding(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos")
    values = ex.sample_values(["ESTADO", "NO_EXISTE"])
    assert sorted(values["ESTADO"]) == ["Activo", "Cancelado"]
    assert "NO_EXISTE" not in values


def test_historical_metrics_need_labels_the_table_does_not_have(bank_db):
    ex = DatabaseExecutor(bank_db, "contratos")
    assert ex.metrics({"CT-1"}, "DQC_X") is None


def test_it_reaches_a_table_in_another_schema(bank_db):
    """A bank table is schema-qualified; ATTACH gives sqlite the same shape."""
    bank_db.execute("ATTACH DATABASE ':memory:' AS RIESGOS")
    bank_db.execute("CREATE TABLE RIESGOS.contratos ("
                    "ID_CONTRATO TEXT, EDAD_CLIENTE INTEGER)")
    bank_db.execute("INSERT INTO RIESGOS.contratos VALUES ('CT-9', 200)")
    bank_db.commit()

    ex = DatabaseExecutor(bank_db, "contratos", schema="RIESGOS")
    assert ex.qualified == '"RIESGOS"."contratos"'
    assert ex.n_rows == 1                       # the schema's table, not the other
    result = ex.run("SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130")
    assert result["ok"] is True, result.get("error")
    assert result["ejemplos"][0]["ID_CONTRATO"] == "CT-9"


# ── the uploaded-file executor keeps its behaviour ───────────────────────────

def _uploaded() -> UploadedTableExecutor:
    csv = (b"ID_CONTRATO;EDAD_CLIENTE\n"
           b"CT-1;140\nCT-2;44\nCT-3;135\n")
    return UploadedTableExecutor(react.load_cases(csv, "mylib.contratos",
                                                  "contratos.csv"),
                                 "mylib.contratos")


def test_the_uploaded_table_executes_the_same_control():
    ex = _uploaded()
    assert ex.n_rows == 3
    result = ex.run("SELECT ID_CONTRATO FROM mylib.contratos "
                    "WHERE EDAD_CLIENTE > 130")
    assert result["ok"] is True
    assert result["n_casos"] == 2


def test_the_uploaded_table_refuses_a_write_too():
    result = _uploaded().run("DROP TABLE contratos")
    assert result["ok"] is False
