# Field Identification Prompt

Eres un experto en calidad de datos regulatorios (IRB / IFRS 9 / BCBS 239).

Dada la siguiente regla de negocio y el diccionario de campos de una tabla,
identifica **todos los campos implicados** que se necesitan para evaluar la regla.

## Regla

{rule}

## Diccionario de campos

{fields_context}

## Instrucciones

1. Lee la regla cuidadosamente.
2. Para cada campo que la regla menciona o necesita, devuelve:
   - El nombre exacto del campo tal como aparece en el diccionario.
   - Una breve descripción de por qué es relevante para la regla.
3. Devuelve la respuesta como JSON:

```json
{
  "fields": [
    {
      "name": "campo_exacto",
      "reason": "explicación breve de su relevancia",
      "data_type": "STRING|NUMBER|DATE|BOOLEAN"
    }
  ],
  "confidence": "HIGH|MEDIUM|LOW"
}
```

4. Si ningún campo del diccionario es relevante, devuelve:
```json
{
  "fields": [],
  "confidence": "LOW",
  "reason": "ningún campo relevante encontrado"
}
```

## BCBS 239 Classification

Además, clasifica la regla según las dimensiones de calidad de BCBS 239:
- **Accuracy**: ¿La regla verifica que los datos son correctos?
- **Completeness**: ¿La regla verifica que no faltan datos?
- **Consistency**: ¿La regla verifica que los datos son consistentes entre tablas?
- **Timeliness**: ¿La regla verifica que los datos están actualizados?
- **Uniqueness**: ¿La regla verifica que no hay duplicados?
- **Validity**: ¿La regla verifica que los datos cumplen un formato/valor?

Devuelve las dimensiones aplicables como un array:
```json
{
  "bcbs239_dimensions": ["Consistency", "Validity"]
}
```