"""Consistency-rule generation for the DQC PoC.

Given the *input table* (its field dictionary Excel) and a *database*
(the schema of the other tables it must stay coherent with — masters, source
tables, reference tables), this router generates cross-field / cross-table /
cardinality consistency checks. Each generated check is a ``DQCItem`` that
persists through the same store as the rest of the pipeline and is classified
against BCBS 239 (consistency checks map to P13 — Reconciliation).

The database schema is supplied as a JSON string::

    {"tables": [{"name": "mylib.maestro_gestores",
                 "columns": [{"name": "COD_GESTOR", "type": "TEXT",
                              "description": "PK gestor"}]}]}

so the generator can reason about foreign keys and cross-table invariants
without needing a live connection to a real database.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.knowledge import get_client
from src.knowledge import bcbs239

from . import dqc as dqc_router
from . import dqc_dictionary as dict_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dqc", tags=["dqc"])


CONSISTENCY_SYSTEM = """\
Eres un experto en coherencia de datos para reporting regulatorio bancario.

Recibes:
1. El diccionario de campos de la TABLA OBJETIVO (la "input table").
2. El esquema de OTRAS TABLAS de la base de datos (maestros, tablas fuente,
   tablas de referencia).

Tu tarea es generar CONTROLES DE CONSISTENCIA que garanticen que la tabla
objetivo es coherente con el resto de la base de datos. Cada control debe
cubrir UNO de estos tipos de incoherencia:
- referencial / integridad: un valor de la tabla objetivo debe existir (o no)
  en otra tabla (clave externa, código huérfano, borrado lógico).
- cross_table: coherencia entre un valor de la tabla objetivo y un valor
  derivado/calculado en otra tabla (reconciliación de totales).
- cross_field: coherencia entre DOS O MÁS campos de la misma tabla
  (un flag exige un valor, una fecha fin tras la de inicio, etc.).
- cardinality: unicidad / multiplicidad (un contrato no puede tener dos ciclos
  abiertos a la vez).

Reglas:
- Usa nombres de campo EXACTOS (MAYÚSCULAS) del diccionario y del esquema.
- La tabla objetivo es la indicada; usa las demás tablas SOLO en joins/EXISTS.
- Cada DQC debe ser una consulta SQL SELECT que devuelve las filas que VIOLAN
  la regla.
- Clasifica cada control en `bcbs239` como "P13 — Reconciliation" (o el
  principio más relevante de BCBS 239).

PRINCIPIOS BCBS 239 (código: nombre):
{BCBS239_PRINCIPLES}

Responde SOLO con JSON: {"dqcs": [...]}. Cada objeto:
{
  "dqc_id": "DQC_<CAMPO>_<NNN>",
  "variable": "<campo principal>",
  "descripcion": "<qué coherencia verifica>",
  "tipo": "consistencia|referencial|cross_table|cross_field|cardinality",
  "severidad": "bloqueante|advertencia|informativo",
  "regla_sql": "<SELECT de filas que violan la regla>",
  "condicion_error": "<cuándo falla la coherencia>",
  "campos_entrada": ["campo1", "campo2"],
  "referencia_regulatoria": "<si aplica, o 'Sin referencia en diccionario'>",
  "umbral": "<si aplica>",
  "periodicidad": "mensual",
  "justificacion": "<por qué>",
  "bcbs239": "P13 — Reconciliation"
}
"""


def _parse_schema(database_schema: str | None) -> list[dict]:
    """Parse the JSON database-schema form field into a list of table dicts."""
    if not database_schema or not database_schema.strip():
        return []
    try:
        parsed = json.loads(database_schema)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400,
                            detail="database_schema must be valid JSON")
    if isinstance(parsed, dict):
        tables = parsed.get("tables", [])
    elif isinstance(parsed, list):
        tables = parsed
    else:
        raise HTTPException(status_code=400,
                            detail="database_schema must be an object or a list")
    clean: list[dict] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "").strip()
        if not name:
            continue
        cols = []
        for c in (t.get("columns") or []):
            if not isinstance(c, dict):
                continue
            cname = str(c.get("name") or "").strip()
            if not cname:
                continue
            cols.append({
                "name": cname,
                "type": str(c.get("type") or "TEXT").strip(),
                "description": str(c.get("description") or "").strip(),
            })
        clean.append({"name": name, "columns": cols})
    return clean


def _schema_text(tables: list[dict]) -> str:
    """Render the database schema for the prompt."""
    lines = []
    for t in tables:
        lines.append(f"- {t['name']}")
        for c in t["columns"]:
            desc = f" — {c['description']}" if c["description"] else ""
            lines.append(f"    {c['name']} ({c['type']}){desc}")
    return "\n".join(lines)


@router.post("/consistency_rules", response_model=dqc_router.GenerateResponse)
async def generate_consistency_rules(
    dictionary: UploadFile = File(..., description="Field dictionary (.xlsx)"),
    database_schema: str | None = Form(
        None, description="JSON schema of the other tables in the database"),
    instructions: str = Form(
        "", description="Optional natural-language consistency rules"),
    table_name: str = Form("mylib.ciclos_recuperacion"),
    sheet: str | None = Form(None, description="Workbook sheet holding the dictionary"),
    column_mapping: str | None = Form(None, description="JSON role->header mapping"),
    infer_formats: bool = Form(True, description="LLM-infer missing field types"),
    project_id: str | None = Form(
        None, description="Data-quality project the generated DQCs belong to"),
) -> dqc_router.GenerateResponse:
    """Generate consistency checks from an input-table dictionary and a
    database schema (other tables). The output persists to the same checks
    store as ``/dqc/generate``, classified against BCBS 239."""
    dqc_router._require_xlsx(dictionary)
    raw = await dictionary.read()

    mapping = dqc_router._parse_mapping_form(column_mapping)
    fields, sheet_used, mapping_source, formats_inferred, agents_used = (
        dqc_router._resolve_dictionary_context(raw, sheet, mapping,
                                               infer_formats,
                                               dictionary.filename))

    tables = _parse_schema(database_schema)
    instr_lines = dqc_router._split_instructions(instructions)
    if not instr_lines:
        instr_lines = [
            "Genera las reglas de coherencia necesarias entre la tabla "
            "objetivo y el resto de la base de datos.",
        ]

    system = CONSISTENCY_SYSTEM.replace(
        "{BCBS239_PRINCIPLES}", bcbs239.describe_principles())
    dict_text, sent = dict_ai.fields_to_text(fields)
    schema_text = _schema_text(tables)
    user = (
        f"Tabla objetivo: {table_name}\n\n"
        f"DICCIONARIO DE LA TABLA OBJETIVO ({sent} campos):\n"
        f"{dict_text}\n"
    )
    if tables:
        user += f"\nOTRAS TABLAS DE LA BASE DE DATOS:\n{schema_text}\n"
    else:
        user += ("\n(No se proporcionó esquema de otras tablas: genera SOLO "
                 "reglas de coherencia entre campos de la tabla objetivo.)\n")
    user += (
        f"\nREGLAS DE CONSISTENCIA ({len(instr_lines)}):\n"
        + "\n".join(f"{i + 1}. {ln}" for i, ln in enumerate(instr_lines))
    )

    dqcs = []
    try:
        result = get_client().chat_json(system=system,
                                        user=user[:dict_ai.PROMPT_CHAR_BUDGET],
                                        max_tokens=4096)
        agents_used += 1
        dqcs = dqc_router._parse_dqc_items(result)
    except Exception as exc:  # noqa: BLE001
        logger.error("consistency generation failed: %s", exc)
        raise HTTPException(status_code=502,
                            detail=f"Consistency generation failed: {exc}")

    dqc_router._dedupe_ids(dqcs)
    try:
        dqc_router._persist_dqc_items(dqcs, project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("persist failed: %s", exc)

    summary = (
        f"Se generaron {len(dqcs)} controles de consistencia a partir de "
        f"{len(fields)} campos de la tabla objetivo"
        + (f" y {len(tables)} tabla(s) de la base de datos" if tables else "")
        + "."
    )
    return dqc_router.GenerateResponse(
        dqcs=dqcs,
        dictionary_fields=len(fields),
        context_summary=summary,
        sheet_used=sheet_used or "",
        mapping_source=mapping_source,
        formats_inferred=formats_inferred,
        agents_used=agents_used,
    )
