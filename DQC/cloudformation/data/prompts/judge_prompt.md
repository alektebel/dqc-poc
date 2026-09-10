# LLM-as-Judge Prompt

Evalúa la calidad de la consulta SQL generada para un DQC.

## Regla de negocio original

{rule}

## Consulta SQL generada

{sql}

## Campos implicados

{fields_json}

## Diccionario de campos (schema)

{table_schema}

## Instrucciones

Evalúa la consulta SQL con los siguientes criterios:

1. **Correctitud semántica**: ¿La consulta implementa correctamente la regla de negocio?
   - Score: 1-5 (5 = implementación perfecta, 1 = completamente incorrecta)
   - Explicación de por qué

2. **Sintaxis**: ¿La consulta es sintácticamente válida para el dialecto especificado?
   - Score: boolean (true/false)
   - Si es false, explicar el error

3. **Cobertura**: ¿La consulta cubre todos los campos implicados necesarios?
   - Score: boolean (true/false)
   - Explicación de campos faltantes si aplica

4. **Detección de fallo**: ¿La consulta identificará correctamente las violaciones?
   - Score: 1-5
   - Incluye una explicación de por qué los registros problemáticos serían detectados

5. **BCBS 239 alignment**: ¿La consulta se alinea con las dimensiones de calidad BCBS 239?
   - Score: boolean (true/false)
   - Explicación

## Output JSON

```json
{
  "semantic_correctness": 4,
  "semantic_explanation": "La consulta implementa correctamente la lógica de consistencia entre campos...",
  "syntax_valid": true,
  "syntax_explanation": null,
  "coverage_complete": true,
  "coverage_explanation": "Todos los campos PD_ESTIMADA, PD_REAL son referenciados",
  "detection_quality": 5,
  "detection_explanation": "El WHERE clause correctamente filtra registros donde PD_ESTIMADA > PD_REAL con umbral del 10%",
  "bcbs_aligned": true,
  "bcbs_explanation": "Consistencia entre campos - dimensión BCBS 239 aplicada correctamente",
  "overall_score": 4.5,
  "recommendation": "APPROVE|REVISE|REJECT",
  "revision_notes": "Si REVISE, indica qué cambiar. Null si APPROVE o REJECT."
}
```