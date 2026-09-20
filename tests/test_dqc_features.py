"""Tests for the new DQC PoC features:
  * BCBS 239 classification (module + fallback on persist)
  * case-explanation endpoint (/dqc/checks/{id}/explain)
  * feedback endpoint (/dqc/checks/{id}/feedback)
"""

from __future__ import annotations

import io
import json
import os
import sqlite3

import pytest

os.environ.setdefault("REGLLM_LLM", "stub")

from fastapi.testclient import TestClient  # noqa: E402

import api.routers.dqc as dqc_router  # noqa: E402
from api.main import app  # noqa: E402
from src.knowledge import bcbs239  # noqa: E402
from training.dq import checks_db  # noqa: E402


class _FakeClient:
    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.calls: list[dict] = []

    def chat_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user})
        return self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]


@pytest.fixture()
def isolated_checks_db(tmp_path, monkeypatch):
    db_path = tmp_path / "checks.db"
    real_connect = checks_db.connect

    def _connect(path=None):
        return real_connect(db_path if path is None else path)

    monkeypatch.setattr(dqc_router.checks_db, "connect", _connect)
    return db_path


@pytest.fixture()
def client(isolated_checks_db):
    return TestClient(app)


def _make_dict_xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Field", "Type", "Description", "Reg Ref"])
    ws.append(["PD_ESTIMADA", "REAL", "Estimated PD", ""])
    ws.append(["EAD_TOTAL", "REAL", "Total EAD", ""])
    ws.append(["COD_GESTOR", "TEXT", "Gestor", "FK maestro_gestores"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_cases_xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["PD_ESTIMADA", "DQC_ID"])
    ws.append([1.5, "DQC_PD_001"])
    ws.append([0.5, ""])
    ws.append([2.0, "DQC_PD_001"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _insert_check(conn, *, status="pending", sql="SELECT 1", name="chk"):
    return checks_db.insert_check(
        conn, name=name, description="desc", severity="HIGH", category="rango",
        sql=sql, status=status)


def _wire(monkeypatch, fake):
    monkeypatch.setattr(dqc_router, "get_client", lambda: fake)
    monkeypatch.setattr(dqc_router, "get_inspect_client", lambda: fake)


# ── BCBS 239 module ──────────────────────────────────────────────────────────

def test_bcbs_principles_have_14_entries():
    assert len(bcbs239.PRINCIPLES) == 14
    assert bcbs239.PRINCIPLES_BY_CODE["P3"].name == "Accuracy and integrity"


def test_bcbs_normalise_accepts_various_forms():
    assert bcbs239.normalise("P3") == "P3"
    assert bcbs239.normalise("BCBS 239 P5") == "P5"
    assert bcbs239.normalise("Principle 13") == "P13"
    assert bcbs239.normalise("raro") == ""


def test_bcbs_display_renders_label():
    assert bcbs239.display("P4") == "P4 — Completeness"


def test_bcbs_default_for_type():
    assert bcbs239.default_for_type("completitud") == "P4"
    assert bcbs239.default_for_type("consistencia") == "P13"


# ── reviewer feedback ────────────────────────────────────────────────────────

def test_feedback_endpoint_roundtrip(client, isolated_checks_db):
    conn = checks_db.connect()
    try:
        cid = _insert_check(conn)
    finally:
        conn.close()
    resp = client.post(f"/dqc/checks/{cid}/feedback",
                       json={"feedback": "El umbral debería ser 0.05"})
    assert resp.status_code == 200
    assert resp.json()["feedback"] == "El umbral debería ser 0.05"
    # persisted
    conn = checks_db.connect()
    try:
        assert checks_db.get_check(conn, cid)["feedback"] == "El umbral debería ser 0.05"
    finally:
        conn.close()


# ── case explanation endpoint ────────────────────────────────────────────────

def test_explain_requires_cases(client, monkeypatch, isolated_checks_db):
    fake = _FakeClient([{}])
    _wire(monkeypatch, fake)
    conn = checks_db.connect()
    try:
        cid = _insert_check(conn)
    finally:
        conn.close()
    resp = client.post(f"/dqc/checks/{cid}/explain")
    assert resp.status_code == 200
    assert resp.json()["available"] is False  # no cases recorded yet


def test_explain_generates_and_caches(client, monkeypatch, isolated_checks_db):
    fake = _FakeClient([
        {"explicacion": "Los casos comparten PD > 1.",
         "factor_comun": "PD fuera de rango", "posible_causa": "captura",
         "recomendacion": "Revisar carga"},
    ])
    _wire(monkeypatch, fake)
    conn = checks_db.connect()
    try:
        cid = _insert_check(conn)
        # seed the cases payload as /evaluate or a generation run would
        conn.execute("""CREATE TABLE IF NOT EXISTS check_eval_cases (
            check_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
            evaluated_at TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO check_eval_cases VALUES (?,?,?)",
            (cid, json.dumps({"columnas": ["PD_ESTIMADA"],
                              "ejemplos": [{"PD_ESTIMADA": "1.5"}],
                              "n_casos": 1}), "2026-01-01T00:00:00Z"))
        conn.commit()
    finally:
        conn.close()

    resp = client.post(f"/dqc/checks/{cid}/explain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["factor_comun"] == "PD fuera de rango"
    # cached on the check row too
    conn = checks_db.connect()
    try:
        assert "Factor común: PD fuera de rango" in checks_db.get_check(conn, cid)["explicacion"]
    finally:
        conn.close()


# ── persist assigns a BCBS 239 fallback when the model omits it ──────────────

def test_persist_assigns_bcbs_fallback(client, monkeypatch, isolated_checks_db):
    fake = _FakeClient([
        {"dqcs": [{
            "dqc_id": "DQC_PD_001", "variable": "PD_ESTIMADA",
            "descripcion": "PD en rango", "tipo": "rango",
            "severidad": "bloqueante",
            "regla_sql": "SELECT * FROM mylib.ciclos_recuperacion WHERE PD_ESTIMADA > 1",
        }]},
    ])
    _wire(monkeypatch, fake)
    resp = client.post(
        "/dqc/generate",
        data={"instructions": "La PD no supera 1", "sheet": "Sheet",
              "column_mapping": json.dumps({"field": "Field", "type": "Type"})},
        files={"dictionary": ("d.xlsx", _make_dict_xlsx(),
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 200
    conn = sqlite3.connect(isolated_checks_db)
    row = conn.execute("SELECT bcbs239, tipo FROM checks").fetchone()
    # rango → P3 fallback, rendered with the principle name
    assert row[0] == "P3 — Accuracy and integrity"
