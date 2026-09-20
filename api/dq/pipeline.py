"""One rule through the agent loop — the unit of work.

Sufficiency → query generation → static and dynamic validation →
correction → attribution → explanation, for ONE rule, with everything it
depends on passed in:

* ``client``   the LLM. A global lookup would have made this module
               untestable in isolation and unconfigurable per invocation.
* ``executor`` where the query runs (:mod:`api.dq.executor`) — the
               uploaded file, or the bank's own database. ``None`` means
               static validation only.

Nothing here imports FastAPI, reads a request or writes to a store, so
the same function body runs inside the API process, inside a thread of a
local batch, or inside a Lambda handling exactly one rule.

The loop is a generator: it yields progress payloads (which the API turns
into SSE frames or job-item updates) and returns a :class:`RuleOutcome`.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from src.knowledge import attribution as attrib
from api.routers import dqc_dictionary as dict_ai
from api.routers import dqc_react as react

logger = logging.getLogger(__name__)


class DQCItem(BaseModel):
    dqc_id: str = ""
    prev_id: str = ""              # previous/official id given by the user
    variable: str = ""
    descripcion: str = ""
    tipo: str = ""
    severidad: str = ""
    regla_sql: str = ""
    condicion_error: str = ""
    campos_entrada: list[str] = []
    referencia_regulatoria: str = ""
    umbral: str = ""
    periodicidad: str = ""
    justificacion: str = ""
    bcbs239: str = ""


def extract_dqc_list(result: Any) -> list[dict]:
    if not isinstance(result, dict):
        return []
    lower_map = {k.lower(): k for k in result}
    for candidate in ("dqcs", "dqc_list", "checks", "controles"):
        real_key = lower_map.get(candidate)
        if real_key and isinstance(result[real_key], list):
            return result[real_key]
    for v in result.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def parse_dqc_items(result: Any) -> list[DQCItem]:
    items: list[DQCItem] = []
    for d in extract_dqc_list(result):
        cleaned: dict[str, Any] = {}
        for k, v in d.items():
            if k not in DQCItem.model_fields or v is None:
                continue
            ft = DQCItem.model_fields[k].annotation
            if ft is str and not isinstance(v, str):
                v = str(v)
            cleaned[k] = v
        items.append(DQCItem(**cleaned))
    return items


class RuleOutcome:
    """What running ONE rule through the agent loop produced."""

    def __init__(self) -> None:
        self.estado: str = "error"          # completado | ambigua | error
        self.items: list[DQCItem] = []
        self.validacion: dict | None = None
        self.trace: list[dict] = []
        self.atribucion: dict | None = None
        self.explicacion: str | None = None
        self.error: str = ""
        self.falta: str = ""
        self.campos: list[str] = []
        self.agents: int = 0
        self.executed: bool = False
        self.metrics: dict | None = None


def run_rule_pipeline(entry: dict, fields: list, table_name: str,
                      executor, *, client,
                      value_grounding: bool = False,
                      semantic_judge: bool = False,
                      seed_feedback: list[str] | None = None):
    """Sufficiency → SAS generation → static/dynamic validation → correction,
    for ONE rule.

    A generator: it yields the progress payloads the SSE stream forwards
    verbatim (``{"id", "estado", "fase", …}``) and returns a
    :class:`RuleOutcome`. ``/dqc/generate_stream`` and the per-revision
    endpoints both drive it, so a rule added one at a time from the rules
    page goes through exactly the same loop as a batch.

    ``seed_feedback`` primes the correction loop with the reviewer's own
    words — what "reejecutar con motivo" sends back.
    """
    eid = entry["id"]
    out = RuleOutcome()
    # decision trace — the audit record behind the UI's validation flow
    trace = out.trace

    # ── 1. sufficiency: do we have everything, or is it ambiguous?
    yield {"id": eid, "estado": "en_curso", "fase": "suficiencia"}
    suf = react.check_sufficiency(entry["regla"], fields, client)
    out.agents += 1
    trace.append({
        "paso": "suficiencia",
        "pregunta": "¿Información suficiente?",
        "resultado": "si" if suf["suficiente"] else "no",
        "detalle": suf["falta"] or suf["interpretacion"],
    })
    if not suf["suficiente"]:
        trace.append({"paso": "resultado", "estado": "ambigua",
                      "detalle": suf["falta"]})
        out.estado = "ambigua"
        out.falta = suf["falta"]
        out.campos = suf["campos"]
        yield {"id": eid, "estado": "ambigua", "falta": suf["falta"],
               "campos": suf["campos"], "trace": trace}
        return out

    # ── optional value grounding: sample real domain values once per rule
    # so the generator compares against values that exist
    valores = None
    if value_grounding and executor is not None:
        yield {"id": eid, "estado": "en_curso", "fase": "grounding"}
        valores = executor.sample_values(
            suf["campos"] or [f.name for f in fields])

    # ── 2-4. generate SAS → validate → correct (fresh agent each try)
    items: list[DQCItem] = []
    validacion: dict | None = None
    feedback: list[str] | None = list(seed_feedback) if seed_feedback else None
    last_errors: list[str] = []
    for intento in range(1, react.MAX_ATTEMPTS + 1):
        yield {"id": eid, "estado": "en_curso", "fase": "generacion",
               "intento": intento}
        trace.append({"paso": "generacion", "intento": intento,
                      "accion": "Generar consulta SAS"})
        try:
            result = react.generate_sas(
                entry["regla"], fields, table_name, client,
                campos=suf["campos"], feedback=feedback, valores=valores)
            out.agents += 1
        except Exception as exc:  # noqa: BLE001
            last_errors = [str(exc)]
            feedback = last_errors
            trace.append({"paso": "validacion",
                          "pregunta": "¿Consulta válida?",
                          "resultado": "no", "detalle": str(exc)})
            continue
        items = parse_dqc_items(result)
        if not items:
            last_errors = ["la respuesta no contenía ningún DQC"]
            feedback = last_errors
            trace.append({"paso": "validacion",
                          "pregunta": "¿Consulta válida?",
                          "resultado": "no", "detalle": last_errors[0]})
            continue

        yield {"id": eid, "estado": "en_curso", "fase": "validacion",
               "intento": intento}
        val_errors = react.static_validate(items[0].regla_sql, fields, table_name)
        validacion = {"estatica": "ok" if not val_errors else "error",
                      "ejecutada": False}
        if not val_errors and executor is not None:
            run = executor.run(items[0].regla_sql)
            if not run["ok"]:
                val_errors = [run["error"]]
            else:
                out.executed = True
                validacion.update({
                    "ejecutada": True,
                    "n_casos": run["n_casos"],
                    "columnas": run["columnas"],
                    "ejemplos": run["ejemplos"],
                })
                m = executor.metrics(run["casos"], entry.get("prev_id"))
                if m:
                    validacion.update(m)
                    out.metrics = m
        trace.append({"paso": "validacion",
                      "pregunta": "¿Consulta válida?",
                      "resultado": "no" if val_errors else "si",
                      "detalle": "; ".join(val_errors)})
        if val_errors:
            last_errors = val_errors
            feedback = val_errors
            items = []
            continue

        # ── optional semantic judge: the query runs, but does it implement
        # THIS rule? A rejection feeds the correction loop.
        if semantic_judge:
            yield {"id": eid, "estado": "en_curso", "fase": "juicio",
                   "intento": intento}
            juicio = react.judge_dqc(
                entry["regla"], items[0].regla_sql, items[0].descripcion,
                items[0].condicion_error, validacion.get("ejemplos"),
                client)
            out.agents += 1
            trace.append({"paso": "juicio",
                          "pregunta": "¿El juez la aprueba?",
                          "resultado": "si" if juicio["correcto"] else "no",
                          "detalle": juicio["motivo"]})
            if not juicio["correcto"]:
                last_errors = [f"juez semántico: {juicio['motivo']}"]
                feedback = last_errors
                items = []
                continue
            validacion["juez_ok"] = True
            validacion["juez_motivo"] = juicio["motivo"]
            validacion["juez_confianza"] = juicio["confianza"]
        break

    if not items:
        error = "; ".join(last_errors) or "sin resultado"
        trace.append({"paso": "resultado", "estado": "error", "detalle": error})
        out.estado = "error"
        out.error = error
        yield {"id": eid, "estado": "error",
               "error": f"No validado tras {react.MAX_ATTEMPTS} intentos: {error}",
               "trace": trace}
        return out

    # ── attribution: which dictionary fields the query demonstrably reads,
    # and — through each field's reg_ref — which PD/LGD paragraphs stand
    # behind it. Parsed from the SQL, so no model call and no guessing.
    atribucion = None
    try:
        units = attrib.units_from_fields(fields)
        report = attrib.attribute_sql_structurally(items[0].regla_sql, units)
        usados = [a.unit.key for a in report.used()]
        citas = report.citations()
        if usados:
            # Free grounding check: the model already declares campos_entrada,
            # so compare what it says it used against what the query reads. A
            # claimed-but-unused field is the shape of a hallucinated
            # justification.
            recon = attrib.reconcile_claimed_fields(
                items[0].regla_sql, items[0].campos_entrada, units)
            # Why each field was in the prompt at all — the retriever already
            # computed this and used to throw it away.
            ranked = dict(zip(
                [f.name for f in fields],
                dict_ai.rank_fields(fields, [entry["regla"]])))
            atribucion = {
                "campos": usados,
                "citas": citas,
                "relevancia": {c: round(ranked.get(c, 0.0), 2) for c in usados},
                **recon,
            }
            detalle = ", ".join(usados)
            if citas:
                detalle += f" — {', '.join(citas)}"
            if recon["unsupported_claim"]:
                detalle += ("; declarados pero no usados: "
                            + ", ".join(recon["unsupported_claim"]))
            trace.append({
                "paso": "atribucion",
                "pregunta": "¿En qué se basa la consulta?",
                "resultado": "no" if recon["unsupported_claim"] else "si",
                "detalle": detalle,
            })
            if validacion is not None:
                validacion["atribucion"] = atribucion
    except Exception:  # noqa: BLE001 - attribution must never break generation
        logger.debug("structural attribution failed", exc_info=True)

    trace.append({"paso": "resultado", "estado": "completado",
                  "n_casos": (validacion or {}).get("n_casos")})

    # ── case explanation: when the query ran and surfaced examples, name what
    # they have in common (one fresh agent, best-effort).
    explicacion = None
    if validacion and validacion.get("ejecutada") and validacion.get("ejemplos"):
        yield {"id": eid, "estado": "en_curso", "fase": "explicacion"}
        explicacion = react.explain_cases(
            rule=items[0].descripcion or entry["regla"],
            descripcion=items[0].descripcion,
            condicion_error=items[0].condicion_error,
            columnas=validacion.get("columnas") or [],
            ejemplos=validacion.get("ejemplos") or [],
            client=client)
        out.agents += 1
        validacion["explicacion"] = explicacion

    for it in items:
        it.prev_id = entry.get("prev_id") or ""

    out.estado = "completado"
    out.items = items
    out.validacion = validacion
    out.atribucion = atribucion
    out.explicacion = explicacion
    yield {"id": eid, "estado": "completado",
           "dqcs": [i.model_dump() for i in items],
           "validacion": validacion,
           "explicacion": explicacion,
           "atribucion": atribucion,
           "trace": trace}
    return out
