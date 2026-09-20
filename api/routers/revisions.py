"""Revisions — the flow the app's four screens walk through.

    home      GET    /dqc/revisions                 list what exists
    paso 1    POST   /dqc/revisions                 name + description + data file
    paso 2    POST   /dqc/revisions/{id}/dictionary  the field dictionary
    paso 3    POST   /dqc/revisions/{id}/rules/preview   interpret one rule
              POST   /dqc/revisions/{id}/rules           keep the previewed one
              POST   /dqc/revisions/{id}/rules/batch     a .txt of rules (SSE)
              GET    /dqc/revisions/{id}/rules           the rules and their state
              POST   /dqc/revisions/{id}/rules/{cid}/rerun   re-derive with a reason
    informe   GET    /dqc/revisions/{id}/report      the centralised query

Generation runs the same agent loop as ``/dqc/generate_stream``
(:func:`api.routers.dqc._run_rule_pipeline`); the only difference is
where the dictionary and the data come from — this router reads the two
files the revision already holds instead of taking them on every call.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from training.dq import checks_db, revisions_db

from . import dqc as dqc_router
from . import dqc_dictionary as dict_ai
from . import dqc_react as react

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dqc/revisions", tags=["revisions"])

MIN_DESCRIPTION = 100          # the form's own floor, enforced server-side too
PREVIEW_TTL_S = 30 * 60        # an unconfirmed interpretation is short-lived
MAX_PREVIEWS = 64

# preview_id → {"revision_id", "item", "validacion", "trace", …, "ts"}.
# In-process on purpose: a preview is seconds old, is shown to one reviewer
# and is worthless after a restart. Confirming it is what makes it durable.
_PREVIEWS: dict[str, dict] = {}


# ── Models ───────────────────────────────────────────────────────────────────

class Revision(BaseModel):
    revision_id: str
    name: str
    description: str
    table_name: str
    data_filename: str | None = None
    data_rows: int = 0
    data_columns: int = 0
    dictionary_filename: str | None = None
    dictionary_fields: int = 0
    status: str = "pendiente"
    created_at: str
    updated_at: str | None = None
    # derived, not stored
    rules_total: int = 0
    rules_validated: int = 0
    rules_rejected: int = 0


class RuleRequest(BaseModel):
    regla: str
    comentario: str = ""       # reviewer's correction, fed to the generator


class ConfirmRequest(BaseModel):
    preview_id: str
    comentario: str = ""


class RerunRequest(BaseModel):
    motivo: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _conn():
    return revisions_db.connect()


def _revision_or_404(conn, revision_id: str) -> dict:
    row = revisions_db.get(conn, revision_id)
    if not row:
        raise HTTPException(status_code=404,
                            detail=f"revisión {revision_id} no encontrada")
    return row


def _rule_counts(conn, revision_id: str) -> dict:
    rows = checks_db.list_checks(conn, project_id=revision_id)
    return {
        "rules_total": len(rows),
        "rules_validated": sum(1 for r in rows if r["status"] == "validated"),
        "rules_rejected": sum(1 for r in rows if r["status"] == "rejected"),
    }


def _as_model(conn, row: dict) -> Revision:
    return Revision(**row, **_rule_counts(conn, row["revision_id"]))


def _data_path(revision_id: str, filename: str) -> Path:
    suffix = ".csv" if filename.lower().endswith(".csv") else ".xlsx"
    return revisions_db.files_dir(revision_id) / f"data{suffix}"


def _dict_path(revision_id: str, filename: str) -> Path:
    suffix = ".csv" if filename.lower().endswith(".csv") else ".xlsx"
    return revisions_db.files_dir(revision_id) / f"dictionary{suffix}"


def _stored(revision_id: str, stem: str) -> Path | None:
    """The stored upload for a revision, whichever extension it has."""
    folder = revisions_db.files_dir(revision_id)
    for suffix in (".xlsx", ".csv"):
        path = folder / f"{stem}{suffix}"
        if path.exists():
            return path
    return None


def _load_context(revision: dict):
    """(fields, cases) from the revision's stored dictionary and data file.

    Both are required to add a rule: without a dictionary the generator
    has no field names to ground on, and without data the control could
    not be executed — which is what the rules screen shows.
    """
    revision_id = revision["revision_id"]
    dict_path = _stored(revision_id, "dictionary")
    if dict_path is None:
        raise HTTPException(
            status_code=409,
            detail="La revisión aún no tiene diccionario. Súbelo en el paso 2.")
    try:
        fields = dict_ai.parse_dictionary(dict_path.read_bytes(),
                                          filename=dict_path.name)
    except Exception as exc:  # noqa: BLE001 — a bad stored file is user data
        raise HTTPException(status_code=400,
                            detail=dqc_router._workbook_read_error(
                                dict_path.name, exc))
    if not fields:
        raise HTTPException(
            status_code=400,
            detail="No se pudo leer ningún campo del diccionario guardado.")

    cases = None
    data_path = _stored(revision_id, "data")
    if data_path is not None:
        try:
            cases = react.load_cases(data_path.read_bytes(),
                                     revision["table_name"], data_path.name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400,
                                detail=dqc_router._workbook_read_error(
                                    data_path.name, exc))
    return fields, cases


def _prune_previews() -> None:
    cutoff = time.time() - PREVIEW_TTL_S
    for key in [k for k, v in _PREVIEWS.items() if v["ts"] < cutoff]:
        _PREVIEWS.pop(key, None)
    while len(_PREVIEWS) > MAX_PREVIEWS:
        _PREVIEWS.pop(next(iter(_PREVIEWS)), None)


def _run_one(regla: str, revision: dict, fields, cases,
             comentario: str = "") -> tuple[dqc_router.RuleOutcome, list[dict]]:
    """Drive the shared agent loop to completion, keeping its events."""
    entry = {"id": 1, "regla": regla, "accion": regla, "prev_id": ""}
    gen = dqc_router._run_rule_pipeline(
        entry, fields, revision["table_name"], cases,
        seed_feedback=[comentario] if comentario.strip() else None)
    events: list[dict] = []
    while True:
        try:
            events.append(next(gen))
        except StopIteration as stop:
            return stop.value, events


def _explanation_text(value) -> str:
    """The explanation agent answers with a structured payload; the screens
    show one paragraph, so flatten it the same way /explain stores it."""
    if isinstance(value, dict):
        return dqc_router._format_explicacion(value)
    return value or ""


def _preview_payload(outcome, preview_id: str) -> dict:
    item = outcome.items[0] if outcome.items else None
    return {
        "preview_id": preview_id,
        "estado": outcome.estado,
        "error": outcome.error,
        "falta": outcome.falta,
        "dqc": item.model_dump() if item else None,
        "validacion": outcome.validacion,
        "explicacion": _explanation_text(outcome.explicacion),
        "atribucion": outcome.atribucion,
        "trace": outcome.trace,
    }


# ── Revisions CRUD ───────────────────────────────────────────────────────────

@router.post("", response_model=Revision, status_code=201)
async def create_revision(
    name: str = Form(...),
    description: str = Form(...),
    table_name: str = Form(""),
    data_file: UploadFile = File(..., description="Data table (.csv/.xlsx)"),
) -> Revision:
    """Step 1: the table under review and what it contains.

    The description floor is the form's rule, repeated here because the
    description is prompt context — a two-word one makes every later
    interpretation worse, and the browser is not where that is enforced.
    """
    name = name.strip()
    description = description.strip()
    if not name:
        raise HTTPException(status_code=400,
                            detail="El nombre de la revisión es obligatorio.")
    if len(description) < MIN_DESCRIPTION:
        raise HTTPException(
            status_code=400,
            detail=f"La descripción debe tener al menos {MIN_DESCRIPTION} "
                   f"caracteres (tiene {len(description)}).")
    dqc_router._require_tabular(data_file, what="data_file")
    raw = await data_file.read()

    table = (table_name.strip()
             or (data_file.filename or "tabla").rsplit(".", 1)[0])
    try:
        cases = react.load_cases(raw, table, data_file.filename)
    except Exception as exc:  # noqa: BLE001 — unreadable upload is a user error
        raise HTTPException(status_code=400,
                            detail=dqc_router._workbook_read_error(
                                data_file.filename, exc))

    conn = _conn()
    try:
        revision_id = revisions_db.create(
            conn, name=name, description=description, table_name=table,
            data_filename=data_file.filename, data_rows=cases.n_rows,
            data_columns=len(cases.headers))
        _data_path(revision_id, data_file.filename or "data.csv").write_bytes(raw)
        return _as_model(conn, revisions_db.get(conn, revision_id))
    finally:
        conn.close()


@router.get("", response_model=list[Revision])
def list_revisions() -> list[Revision]:
    conn = _conn()
    try:
        return [_as_model(conn, r) for r in revisions_db.list_all(conn)]
    finally:
        conn.close()


@router.get("/{revision_id}", response_model=Revision)
def get_revision(revision_id: str) -> Revision:
    conn = _conn()
    try:
        return _as_model(conn, _revision_or_404(conn, revision_id))
    finally:
        conn.close()


@router.delete("/{revision_id}")
def delete_revision(revision_id: str) -> dict:
    conn = _conn()
    try:
        _revision_or_404(conn, revision_id)
        revisions_db.delete(conn, revision_id)
        return {"deleted": revision_id}
    finally:
        conn.close()


@router.post("/{revision_id}/dictionary", response_model=Revision)
async def upload_dictionary(
    revision_id: str,
    dictionary: UploadFile = File(..., description="Field dictionary (.csv/.xlsx)"),
    sheet: str | None = Form(None),
) -> Revision:
    """Step 2: the dictionary, parsed once here so the user learns at
    upload time that it is unreadable — not on the first rule."""
    conn = _conn()
    try:
        _revision_or_404(conn, revision_id)
        dqc_router._require_tabular(dictionary)
        raw = await dictionary.read()
        try:
            fields = dict_ai.parse_dictionary(raw, sheet=sheet,
                                              filename=dictionary.filename)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400,
                                detail=dqc_router._workbook_read_error(
                                    dictionary.filename, exc))
        if not fields:
            raise HTTPException(
                status_code=400,
                detail="No se reconoció ningún campo. Se esperan columnas tipo "
                       "Campo/Field, Tipo/Type y Descripción/Description.")
        _dict_path(revision_id,
                   dictionary.filename or "dictionary.csv").write_bytes(raw)
        revisions_db.update(conn, revision_id,
                            dictionary_filename=dictionary.filename,
                            dictionary_fields=len(fields))
        return _as_model(conn, revisions_db.get(conn, revision_id))
    finally:
        conn.close()


# ── Rules ────────────────────────────────────────────────────────────────────

@router.get("/{revision_id}/rules")
def list_rules(revision_id: str) -> dict:
    """The rules of this revision, each with its last execution."""
    conn = _conn()
    try:
        _revision_or_404(conn, revision_id)
        rows = checks_db.list_checks(conn, project_id=revision_id)
        conn.execute(dqc_router._EVAL_CASES_SCHEMA)
        cases = {r["check_id"]: json.loads(r["payload"]) for r in conn.execute(
            "SELECT check_id, payload FROM check_eval_cases")}
        rules = []
        for row in rows:
            payload = cases.get(row["check_id"], {})
            rules.append({**row,
                          "n_casos": payload.get("n_casos"),
                          "columnas": payload.get("columnas", []),
                          "ejemplos": payload.get("ejemplos", []),
                          "trace": payload.get("trace", []),
                          "atribucion": payload.get("atribucion"),
                          "explicacion": _explanation_text(
                              payload.get("explicacion"))})
        return {"revision_id": revision_id, "rules": rules,
                **_rule_counts(conn, revision_id)}
    finally:
        conn.close()


@router.post("/{revision_id}/rules/preview")
def preview_rule(revision_id: str, body: RuleRequest) -> dict:
    """Interpret ONE rule without keeping it: the modal the reviewer reads
    before deciding. Nothing is stored until it is confirmed."""
    if not body.regla.strip():
        raise HTTPException(status_code=400, detail="La regla está vacía.")
    conn = _conn()
    try:
        revision = _revision_or_404(conn, revision_id)
    finally:
        conn.close()

    fields, cases = _load_context(revision)
    outcome, _ = _run_one(body.regla.strip(), revision, fields, cases,
                          body.comentario)

    preview_id = f"prev_{uuid.uuid4().hex[:12]}"
    _prune_previews()
    _PREVIEWS[preview_id] = {"revision_id": revision_id,
                             "regla": body.regla.strip(),
                             "outcome": outcome, "ts": time.time()}
    return _preview_payload(outcome, preview_id)


@router.post("/{revision_id}/rules")
def confirm_rule(revision_id: str, body: ConfirmRequest) -> dict:
    """Keep a previewed interpretation as a control of this revision."""
    entry = _PREVIEWS.pop(body.preview_id, None)
    if entry is None or entry["revision_id"] != revision_id:
        raise HTTPException(
            status_code=404,
            detail="La interpretación ha caducado. Vuelve a revisarla.")
    outcome = entry["outcome"]
    if outcome.estado != "completado" or not outcome.items:
        raise HTTPException(
            status_code=409,
            detail="Esa interpretación no produjo un control ejecutable.")

    saved = dqc_router._persist_dqc_items(outcome.items, revision_id)
    if not saved:
        raise HTTPException(status_code=409,
                            detail="El control no pudo guardarse.")
    check_id = saved[0][1]
    dqc_router._save_check_cases([
        (check_id, {**(outcome.validacion or {}),
                    "trace": outcome.trace,
                    **({"atribucion": outcome.atribucion}
                       if outcome.atribucion else {})})])
    conn = _conn()
    try:
        if body.comentario.strip():
            checks_db.set_feedback(conn, check_id, body.comentario.strip())
        revisions_db.update(conn, revision_id, status="completada")
        return {"check_id": check_id,
                **(checks_db.get_check(conn, check_id) or {})}
    finally:
        conn.close()


@router.post("/{revision_id}/rules/batch")
async def batch_rules(
    revision_id: str,
    rules_file: UploadFile | None = File(None, description=".txt, one rule per line"),
    rules: str = Form(""),
):
    """A rules file (or a block of lines): every rule through the same loop,
    streamed as SSE so the screen ticks them off, and stored as it goes."""
    from fastapi.responses import StreamingResponse

    conn = _conn()
    try:
        revision = _revision_or_404(conn, revision_id)
    finally:
        conn.close()

    raw = await rules_file.read() if rules_file and rules_file.filename else None
    lines = dqc_router._collect_rules(
        rules, rules_file.filename if rules_file else None, raw)
    fields, cases = _load_context(revision)

    def event_stream():
        conn = _conn()
        try:
            revisions_db.update(conn, revision_id, status="en_ejecucion")
        finally:
            conn.close()
        yield dqc_router._sse("meta", {"reglas": len(lines),
                                       "dictionary_fields": len(fields),
                                       "casos": cases.n_rows if cases else 0})
        yield dqc_router._sse("plan", {"items": [
            {"id": i, "regla": line, "estado": "pendiente"}
            for i, line in enumerate(lines, start=1)]})

        guardados = 0
        fallidas = 0
        for i, line in enumerate(lines, start=1):
            entry = {"id": i, "regla": line, "accion": line, "prev_id": ""}
            gen = dqc_router._run_rule_pipeline(
                entry, fields, revision["table_name"], cases)
            outcome = None
            while True:
                try:
                    yield dqc_router._sse("item", next(gen))
                except StopIteration as stop:
                    outcome = stop.value
                    break
            if outcome.estado != "completado" or not outcome.items:
                fallidas += 1
                continue
            saved = dqc_router._persist_dqc_items(outcome.items, revision_id)
            dqc_router._save_check_cases([
                (cid, {**(outcome.validacion or {}),
                       "trace": outcome.trace,
                       **({"atribucion": outcome.atribucion}
                          if outcome.atribucion else {})})
                for _, cid in saved])
            guardados += len(saved)
            yield dqc_router._sse("guardado", {
                "id": i, "check_ids": [cid for _, cid in saved]})

        conn = _conn()
        try:
            revisions_db.update(
                conn, revision_id,
                status="completada" if guardados else "error")
        finally:
            conn.close()
        yield dqc_router._sse("done", {"guardados": guardados,
                                       "fallidas": fallidas,
                                       "reglas": len(lines)})

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{revision_id}/rules/{check_id}/rerun")
def rerun_rule(revision_id: str, check_id: str, body: RerunRequest) -> dict:
    """Re-derive an existing control, with the reviewer's reason as the
    correction fed to the generator, and re-execute it on the data.

    The control keeps its id and its review history: this is the same
    rule, re-interpreted.
    """
    if not body.motivo.strip():
        raise HTTPException(status_code=400,
                            detail="Explica por qué quieres reejecutar la regla.")
    conn = _conn()
    try:
        revision = _revision_or_404(conn, revision_id)
        check = checks_db.get_check(conn, check_id)
        if not check or check.get("project_id") != revision_id:
            raise HTTPException(
                status_code=404,
                detail=f"El control {check_id} no pertenece a esta revisión.")
    finally:
        conn.close()

    regla = check["description"] or check["name"]
    fields, cases = _load_context(revision)
    outcome, _ = _run_one(regla, revision, fields, cases, body.motivo.strip())
    if outcome.estado != "completado" or not outcome.items:
        raise HTTPException(
            status_code=409,
            detail=f"La reejecución no produjo un control válido: "
                   f"{outcome.error or outcome.falta}")

    item = outcome.items[0]
    conn = _conn()
    try:
        checks_db.set_sql(conn, check_id, sql=item.regla_sql,
                          description=item.descripcion,
                          condicion_error=item.condicion_error,
                          campos_entrada=item.campos_entrada)
        checks_db.set_feedback(conn, check_id, body.motivo.strip())
        dqc_router._save_check_cases([
            (check_id, {**(outcome.validacion or {}),
                        "trace": outcome.trace,
                        **({"atribucion": outcome.atribucion}
                           if outcome.atribucion else {})})])
        return {"check_id": check_id,
                **(checks_db.get_check(conn, check_id) or {}),
                "validacion": outcome.validacion,
                "trace": outcome.trace,
                "explicacion": _explanation_text(outcome.explicacion)}
    finally:
        conn.close()


# ── Report ───────────────────────────────────────────────────────────────────

@router.get("/{revision_id}/report")
def report(revision_id: str) -> dict:
    """The revision's controls, their detected cases and the centralised
    query: every validated control folded into one UNION ALL rowset."""
    conn = _conn()
    try:
        revision = _revision_or_404(conn, revision_id)
        counts = checks_db.counts(conn, revision_id)
        validated = checks_db.export_validated(conn, revision_id)
        sql = checks_db.build_dashboard_query(
            conn, status="validated", project_id=revision_id) if validated else None
        conn.execute(dqc_router._EVAL_CASES_SCHEMA)
        cases = {r["check_id"]: json.loads(r["payload"]) for r in conn.execute(
            "SELECT check_id, payload FROM check_eval_cases")}
        return {
            "revision": _as_model(conn, revision).model_dump(),
            "counts": counts,
            "sql": sql,
            "checks": [{**c, "n_casos": cases.get(c["check_id"], {}).get("n_casos")}
                       for c in validated],
        }
    finally:
        conn.close()
