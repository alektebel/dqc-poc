"""The revision flow the four screens drive: create → dictionary → rules
→ report, plus the CSV uploads the forms take.

The agent loop itself is covered by ``test_dqc_generate_stream.py``; here
the fake client only needs to answer enough for one rule to come out the
far end, so the tests are about persistence, scoping and the HTTP
contract rather than generation quality.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("REGLLM_LLM", "stub")

from fastapi.testclient import TestClient  # noqa: E402

import api.routers.dqc as dqc_router  # noqa: E402
from api.routers import revisions as rev_router  # noqa: E402
from api.main import app  # noqa: E402
from training.dq import checks_db, revisions_db  # noqa: E402

DATA_CSV = (
    "ID_CONTRATO;EDAD_CLIENTE;FECHA_CONCESION\n"
    "CT-1;140;2020-05-12\n"
    "CT-2;44;2019-11-03\n"
    "CT-3;135;2021-01-20\n"
).encode()

DICT_CSV = (
    "Campo,Tipo,Descripcion\n"
    "ID_CONTRATO,TEXT,Identificador del contrato\n"
    "EDAD_CLIENTE,INTEGER,Edad del cliente en anios\n"
    "FECHA_CONCESION,DATE,Fecha de concesion\n"
).encode()

DESCRIPTION = ("Tabla de contratos hipotecarios con granularidad de contrato. "
               "La clave primaria es ID_CONTRATO y recoge edades e importes.")

GOOD_SQL = "SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130"


class _FakeClient:
    """Answers sufficiency, then generation, then anything else.

    ``botch`` makes every rule whose text contains that word come back
    with a query over a column the dictionary does not have, so static
    validation rejects it — one failing rule among good ones.
    """

    def __init__(self, sql: str = GOOD_SQL, botch: str = ""):
        self.sql = sql
        self.botch = botch
        self.calls: list[dict] = []

    def chat_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user})
        if self.botch and self.botch in user and "suficiente" not in system:
            return {"dqcs": [{
                "dqc_id": "DQC_MALO", "variable": "NO_EXISTE",
                "descripcion": "control sobre un campo inexistente",
                "tipo": "rango", "severidad": "advertencia",
                "regla_sql": "SELECT NO_EXISTE FROM contratos WHERE NO_EXISTE > 1",
                "condicion_error": "NO_EXISTE > 1",
                "campos_entrada": ["NO_EXISTE"],
            }]}
        if "suficiente" in system:
            return {"suficiente": True, "campos": ["EDAD_CLIENTE", "ID_CONTRATO"],
                    "interpretacion": "rango máximo sobre la edad", "falta": ""}
        if "dqcs" in system or "DQC" in system:
            return {"dqcs": [{
                "dqc_id": "DQC_EDAD_001", "variable": "EDAD_CLIENTE",
                "descripcion": "La edad del cliente no puede superar 130 años",
                "tipo": "rango", "severidad": "bloqueante",
                "regla_sql": self.sql, "condicion_error": "EDAD_CLIENTE > 130",
                "campos_entrada": ["EDAD_CLIENTE"],
            }]}
        return {}


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "checks.db"
    real_connect = checks_db.connect

    def _connect(path=None):
        return real_connect(db_path if path is None else path)

    monkeypatch.setattr(checks_db, "connect", _connect)
    monkeypatch.setattr(revisions_db, "FILES_DIR", tmp_path / "revisions")
    rev_router._PREVIEWS.clear()
    return db_path


@pytest.fixture()
def fake(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(dqc_router, "get_client", lambda: client)
    monkeypatch.setattr(dqc_router, "get_inspect_client", lambda: client)
    return client


@pytest.fixture()
def client(isolated):
    return TestClient(app)


def _create(client, description: str = DESCRIPTION, data: bytes = DATA_CSV,
            filename: str = "contratos.csv"):
    return client.post("/dqc/revisions",
                       data={"name": "Control Hipotecas", "description": description,
                             "table_name": "contratos"},
                       files={"data_file": (filename, data, "text/csv")})


def _with_dictionary(client) -> str:
    rid = _create(client).json()["revision_id"]
    resp = client.post(f"/dqc/revisions/{rid}/dictionary",
                       files={"dictionary": ("dicc.csv", DICT_CSV, "text/csv")})
    assert resp.status_code == 200, resp.text
    return rid


# ── step 1: the data table ───────────────────────────────────────────────────

def test_create_revision_reads_a_csv(client):
    resp = _create(client)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["data_rows"] == 3          # header row is not a row
    assert body["data_columns"] == 3
    assert body["status"] == "pendiente"
    assert body["rules_total"] == 0


def test_create_revision_rejects_a_short_description(client):
    resp = _create(client, description="Contratos.")
    assert resp.status_code == 400
    assert "100" in resp.json()["detail"]


def test_create_revision_rejects_a_corrupt_workbook(client):
    resp = _create(client, data=b"not a zip", filename="contratos.xlsx")
    assert resp.status_code == 400
    assert "No se pudo leer el fichero" in resp.json()["detail"]


def test_revision_listing_and_deletion(client):
    rid = _create(client).json()["revision_id"]
    assert [r["revision_id"] for r in client.get("/dqc/revisions").json()] == [rid]
    assert client.delete(f"/dqc/revisions/{rid}").status_code == 200
    assert client.get("/dqc/revisions").json() == []
    assert client.get(f"/dqc/revisions/{rid}").status_code == 404


# ── step 2: the dictionary ───────────────────────────────────────────────────

def test_dictionary_upload_counts_fields(client):
    rid = _create(client).json()["revision_id"]
    resp = client.post(f"/dqc/revisions/{rid}/dictionary",
                       files={"dictionary": ("dicc.csv", DICT_CSV, "text/csv")})
    assert resp.status_code == 200, resp.text
    assert resp.json()["dictionary_fields"] == 3
    assert resp.json()["dictionary_filename"] == "dicc.csv"


def test_dictionary_without_recognisable_columns_is_400(client):
    rid = _create(client).json()["revision_id"]
    resp = client.post(f"/dqc/revisions/{rid}/dictionary",
                       files={"dictionary": ("dicc.csv", b"a,b\n1,2\n", "text/csv")})
    assert resp.status_code == 400


def test_rules_need_a_dictionary_first(client, fake):
    rid = _create(client).json()["revision_id"]
    resp = client.post(f"/dqc/revisions/{rid}/rules/preview",
                       json={"regla": "La edad no puede superar 130 años."})
    assert resp.status_code == 409
    assert "diccionario" in resp.json()["detail"]


# ── step 3: rules ────────────────────────────────────────────────────────────

def test_preview_interprets_and_executes_without_storing(client, fake):
    rid = _with_dictionary(client)
    resp = client.post(f"/dqc/revisions/{rid}/rules/preview",
                       json={"regla": "La edad no puede superar 130 años."})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "completado"
    assert body["dqc"]["regla_sql"] == GOOD_SQL
    # it ran against the uploaded CSV: two rows are over 130
    assert body["validacion"]["ejecutada"] is True
    assert body["validacion"]["n_casos"] == 2
    assert [step["paso"] for step in body["trace"]][:2] == ["suficiencia", "generacion"]
    # nothing is persisted until the reviewer confirms
    assert client.get(f"/dqc/revisions/{rid}/rules").json()["rules_total"] == 0


def test_confirm_stores_the_previewed_rule_with_its_cases(client, fake):
    rid = _with_dictionary(client)
    preview = client.post(f"/dqc/revisions/{rid}/rules/preview",
                          json={"regla": "La edad no puede superar 130 años."}).json()
    resp = client.post(f"/dqc/revisions/{rid}/rules",
                       json={"preview_id": preview["preview_id"],
                             "comentario": "Aplicar solo a contratos vivos."})
    assert resp.status_code == 200, resp.text
    check_id = resp.json()["check_id"]

    rules = client.get(f"/dqc/revisions/{rid}/rules").json()
    assert rules["rules_total"] == 1
    rule = rules["rules"][0]
    assert rule["check_id"] == check_id
    assert rule["n_casos"] == 2
    assert rule["feedback"] == "Aplicar solo a contratos vivos."
    assert rule["sql"] == GOOD_SQL


def test_a_preview_can_only_be_confirmed_once(client, fake):
    rid = _with_dictionary(client)
    preview = client.post(f"/dqc/revisions/{rid}/rules/preview",
                          json={"regla": "La edad no puede superar 130 años."}).json()
    body = {"preview_id": preview["preview_id"]}
    assert client.post(f"/dqc/revisions/{rid}/rules", json=body).status_code == 200
    assert client.post(f"/dqc/revisions/{rid}/rules", json=body).status_code == 404


def test_rules_are_scoped_to_their_revision(client, fake):
    first = _with_dictionary(client)
    second = _with_dictionary(client)
    preview = client.post(f"/dqc/revisions/{first}/rules/preview",
                          json={"regla": "La edad no puede superar 130 años."}).json()
    client.post(f"/dqc/revisions/{first}/rules",
                json={"preview_id": preview["preview_id"]})
    assert client.get(f"/dqc/revisions/{first}/rules").json()["rules_total"] == 1
    assert client.get(f"/dqc/revisions/{second}/rules").json()["rules_total"] == 0


def _await_job(client, rid, job_id, timeout=30.0):
    """Poll the job the way the screen does, until it settles."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/dqc/revisions/{rid}/jobs/{job_id}").json()
        if job["status"] in ("completado", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} no terminó: {job}")


def test_batch_queues_a_job_and_stores_every_rule(client, fake):
    rid = _with_dictionary(client)
    rules_txt = ("La edad del cliente no puede superar 130 años.\n"
                 "La fecha de concesión debe ser anterior a la de vencimiento.\n")
    resp = client.post(f"/dqc/revisions/{rid}/rules/batch",
                       files={"rules_file": ("reglas.txt", rules_txt.encode(),
                                             "text/plain")})
    # the request returns immediately: the work is not inside it
    assert resp.status_code == 202, resp.text
    assert resp.json()["total"] == 2
    job_id = resp.json()["job_id"]

    job = _await_job(client, rid, job_id)
    assert job["status"] == "completado"
    assert job["saved"] == 2 and job["failed"] == 0
    assert [i["status"] for i in job["items"]] == ["completado", "completado"]
    assert all(i["check_id"] for i in job["items"])
    assert client.get(f"/dqc/revisions/{rid}/rules").json()["rules_total"] == 2


def test_a_failing_rule_does_not_sink_the_batch(client, monkeypatch):
    """The whole point of one worker per rule: a rule that cannot be
    derived marks its own row and the others still land."""
    botched = _FakeClient(botch="vencimiento")
    monkeypatch.setattr(dqc_router, "get_client", lambda: botched)
    monkeypatch.setattr(dqc_router, "get_inspect_client", lambda: botched)

    rid = _with_dictionary(client)
    rules_txt = ("La edad del cliente no puede superar 130 años.\n"
                 "La fecha de concesión debe ser anterior a la de vencimiento.\n")
    job_id = client.post(f"/dqc/revisions/{rid}/rules/batch",
                         files={"rules_file": ("reglas.txt", rules_txt.encode(),
                                               "text/plain")}).json()["job_id"]

    job = _await_job(client, rid, job_id)
    assert job["status"] == "completado"       # the job itself did not crash
    assert job["saved"] == 1 and job["failed"] == 1
    estados = {i["regla"]: i["status"] for i in job["items"]}
    assert estados["La edad del cliente no puede superar 130 años."] == "completado"
    assert estados["La fecha de concesión debe ser anterior a la de vencimiento."] == "error"
    bad = [i for i in job["items"] if i["status"] == "error"][0]
    assert "NO_EXISTE" in bad["error"]
    assert client.get(f"/dqc/revisions/{rid}/rules").json()["rules_total"] == 1


def test_job_progress_is_visible_while_it_runs(client, fake):
    rid = _with_dictionary(client)
    resp = client.post(f"/dqc/revisions/{rid}/rules/batch",
                       data={"rules": "La edad del cliente no puede superar 130 años."})
    job_id = resp.json()["job_id"]
    # every rule has a row from the moment the job is created
    job = client.get(f"/dqc/revisions/{rid}/jobs/{job_id}").json()
    assert len(job["items"]) == 1
    assert job["items"][0]["regla"].startswith("La edad")
    _await_job(client, rid, job_id)
    assert client.get(f"/dqc/revisions/{rid}/jobs").json()["job_id"] == job_id


def test_job_of_another_revision_is_not_readable(client, fake):
    first = _with_dictionary(client)
    second = _with_dictionary(client)
    job_id = client.post(f"/dqc/revisions/{first}/rules/batch",
                         data={"rules": "La edad no puede superar 130."}).json()["job_id"]
    _await_job(client, first, job_id)
    assert client.get(f"/dqc/revisions/{second}/jobs/{job_id}").status_code == 404


def test_rerun_rederives_the_same_control(client, fake):
    rid = _with_dictionary(client)
    preview = client.post(f"/dqc/revisions/{rid}/rules/preview",
                          json={"regla": "La edad no puede superar 130 años."}).json()
    check_id = client.post(f"/dqc/revisions/{rid}/rules",
                           json={"preview_id": preview["preview_id"]}).json()["check_id"]

    fake.sql = "SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 120"
    resp = client.post(f"/dqc/revisions/{rid}/rules/{check_id}/rerun",
                       json={"motivo": "El umbral correcto es 120, no 130."})
    assert resp.status_code == 200, resp.text
    assert resp.json()["check_id"] == check_id          # same control, re-derived
    assert resp.json()["sql"].endswith("> 120")
    assert resp.json()["feedback"] == "El umbral correcto es 120, no 130."
    # still one rule, and the reviewer's reason went into the generator
    assert client.get(f"/dqc/revisions/{rid}/rules").json()["rules_total"] == 1
    assert any("120, no 130" in call["user"] for call in fake.calls)


def test_rerun_needs_a_reason(client, fake):
    rid = _with_dictionary(client)
    resp = client.post(f"/dqc/revisions/{rid}/rules/whatever/rerun",
                       json={"motivo": "   "})
    assert resp.status_code == 400


def test_rerun_refuses_a_control_of_another_revision(client, fake):
    first = _with_dictionary(client)
    second = _with_dictionary(client)
    preview = client.post(f"/dqc/revisions/{first}/rules/preview",
                          json={"regla": "La edad no puede superar 130 años."}).json()
    check_id = client.post(f"/dqc/revisions/{first}/rules",
                           json={"preview_id": preview["preview_id"]}).json()["check_id"]
    resp = client.post(f"/dqc/revisions/{second}/rules/{check_id}/rerun",
                       json={"motivo": "cualquier cosa"})
    assert resp.status_code == 404


# ── the report ───────────────────────────────────────────────────────────────

def test_report_is_scoped_to_the_revision(client, fake):
    first = _with_dictionary(client)
    second = _with_dictionary(client)
    for rid in (first, second):
        preview = client.post(f"/dqc/revisions/{rid}/rules/preview",
                              json={"regla": "La edad no puede superar 130."}).json()
        cid = client.post(f"/dqc/revisions/{rid}/rules",
                          json={"preview_id": preview["preview_id"]}).json()["check_id"]
        if rid == first:
            client.post(f"/dqc/checks/{cid}/status", json={"status": "validated"})

    report = client.get(f"/dqc/revisions/{first}/report").json()
    assert report["counts"]["validated"] == 1
    assert report["counts"]["pending_visible"] == 0      # the other one is not ours
    assert len(report["checks"]) == 1
    assert report["sql"] and "UNION ALL" not in report["sql"]   # a single control

    other = client.get(f"/dqc/revisions/{second}/report").json()
    assert other["counts"]["validated"] == 0
    assert other["sql"] is None
