# SQL Generation Prompt

Eres un experto en SQL y calidad de datos regulatorios (IRB / IFRS 9 / BCBS 239).

Dada una regla de negocio, los campos implicados identificados y el diccionario
de campos, genera una consulta SQL que detecte registros que violen la regla.

## Regla de negocio

{rule}

## Campos implicados

{fields_json}

## Diccionario de campos

{table_schema}

## Instrucciones

1. Genera una consulta SQL válida que seleccione las filas que **violan** la regla.
2. La consulta debe usar el dialecto SQL especificado (`dialect`).
3. Incluye un comentario SQL que explique la lógica de detección.
4. Devuelve la respuesta como JSON:

```json
{
  "sql": "SELECT ... FROM ... WHERE ...",
  "dialect": "postgres|mysql|bigquery|snowflake",
  "description": "Explicación de la consulta",
  "tables_referenced": ["tabla1", "tabla2"],
  "bcbs239_dimensions": ["Consistency", "Validity"],
  "validation_failed_reason": "Explicación de por qué un DQC fallaría para ciertos registros"
}
```

5. **validation_failed_reason**: Para cada DQC generado, debe incluir una razón
   inicial por la que sospecha que los registros no sean adecuados. Esto es
   requerido por la regla #1 del proyecto.

## Validación de sintaxis

Si la consulta generada no es sintácticamente completa o válida:
- Identifica el error específico.
- Reescribe la consulta corrigiendo el error.
- Indica "retry" en el campo "status" con el número de reintento.

```json
{
  "sql": null,
  "status": "retry",
  "retry_attempt": 2,
  "error": "Column 'PD_ESTIMADA' does not exist in table 'exposures'",
  "suggestion": "Use 'pd_estimate' instead"
}
```