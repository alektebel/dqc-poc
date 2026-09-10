"""Tests for the Generar approach 1b (one rule per row):
  * POST /dqc/recognize — live (LLM-free) field recognition
"""

from __future__ import annotations

import io
import json
import os

import pytest

os.environ.setdefault("REGLLM_LLM", "stub")

from fastapi.testclient import TestClient  # noqa: E402

import api.routers.dqc as dqc_router  # noqa: E402
from api.main import app  # noqa: E402
from training.dq import checks_db  # noqa: E402


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
    ws.append(["Field", "Type", "Description"])
    ws.append(["PD_ESTIMADA", "REAL", "Estimated PD"])
    ws.append(["EAD_TOTAL", "REAL", "Total EAD"])
    ws.append(["COD_GESTOR", "TEXT", "Gestor"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dict_form():
    return {"dictionary": ("d.xlsx", _make_dict_xlsx(),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def _extra(data=None):
    out = {"sheet": "Sheet", "column_mapping": json.dumps({"field": "Field", "type": "Type"})}
    if data:
        out.update(data)
    return out


def test_recognize_maps_rules_to_fields(client, isolated_checks_db):
    data = _extra({"rules": json.dumps(["La PD estimada debe estar entre 0 y 1",
                                        "El COD_GESTOR debe existir en el maestro",
                                        "El importe no puede ser negativo"])})
    r = client.post("/dqc/recognize", data=data, files=_dict_form())
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    # exact-name matches recognised, no match flagged ambiguous
    assert results[0]["campos"] == ["PD_ESTIMADA"]
    assert results[0]["ambiguity"] is False
    assert results[1]["campos"] == ["COD_GESTOR"]
    assert results[1]["ambiguity"] is False
    assert results[2]["campos"] == []
    assert results[2]["ambiguity"] is True


def test_recognize_accepts_newline_text(client, isolated_checks_db):
    data = _extra({"rules": "La PD estimada debe estar entre 0 y 1\nEl EAD total no puede ser negativo"})
    r = client.post("/dqc/recognize", data=data, files=_dict_form())
    assert r.status_code == 200
    results = r.json()["results"]
    assert [x["campos"] for x in results] == [["PD_ESTIMADA"], ["EAD_TOTAL"]]
