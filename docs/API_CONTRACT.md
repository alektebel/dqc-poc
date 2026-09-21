# La API que tienes que montar

El frontend no tiene servidor propio. Habla con **una sola URL**, la que
pongas en `web/assets/config.js`, con cuatro rutas. Este documento dice
qué debe recibir y devolver cada una.

```
web/  (estático)  ──HTTPS──▶  TU API  ──▶  Bedrock
                                  └──▶  DynamoDB
```

**Por qué hay una API en medio y no se llama a Bedrock desde el navegador**:
invocar Bedrock exige firmar cada petición con SigV4, es decir, credenciales
de AWS en el cliente. Cualquiera abre el inspector y se las lleva. Lo mismo
vale para DynamoDB. La clave de AWS vive en tu Lambda; el navegador solo
conoce la URL y, como mucho, una API key que no sirve para nada más.

---

## Configuración del cliente

`web/assets/config.js`, el único fichero que tocas:

```js
export const CONFIG = {
  BASE_URL: 'https://abc123.execute-api.eu-west-1.amazonaws.com/prod',
  API_KEY: '…',                 // opcional
  API_KEY_HEADER: 'x-api-key',
  TIMEOUT_S: 120,
};
```

Con `BASE_URL` vacía la app funciona en **modo local** (ver el final).

**CORS**: el navegador enviará `OPTIONS` antes de cada POST. Tu API debe
responder con `Access-Control-Allow-Origin` (el origen desde el que sirvas
`web/`), `Access-Control-Allow-Headers: content-type, x-api-key` y
`Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS`. Si te salen
errores de CORS antes de ver una sola respuesta, es esto.

---

## 1. `POST /llm/interpret` — de la regla a la consulta

Lo único que toca Bedrock. Recibe la regla en lenguaje natural y el
diccionario de campos; devuelve la consulta y cómo la interpretó.

**Petición**

```json
{
  "regla": "La edad del cliente no puede ser mayor de 130 años.",
  "tabla": "contratos",
  "campos": [
    {"nombre": "ID_CONTRATO",     "tipo": "TEXT",    "descripcion": "Identificador del contrato"},
    {"nombre": "EDAD_CLIENTE",    "tipo": "INTEGER", "descripcion": "Edad del cliente en años"},
    {"nombre": "FECHA_CONCESION", "tipo": "DATE",    "descripcion": "Fecha de concesión"}
  ],
  "valores_ejemplo": {"EDAD_CLIENTE": ["44", "61", "135", "140"]},
  "comentario": "El umbral correcto son 120 años, no 130."
}
```

`comentario` llega vacío la primera vez y con el texto del revisor cuando
pulsa "Reejecutar interpretación": es la corrección, y tu prompt debería
dársela al modelo como tal.

`valores_ejemplo` son valores reales que el navegador ha leído del fichero.
Sirven para que el modelo no invente comparaciones contra valores que no
existen. Puedes ignorarlos.

**Respuesta 200**

```json
{
  "estado": "completado",
  "dqc": {
    "descripcion": "La edad del cliente no puede superar 130 años",
    "tipo": "rango",
    "severidad": "bloqueante",
    "campos_entrada": ["EDAD_CLIENTE"],
    "condicion_error": "EDAD_CLIENTE > 130",
    "sql": "SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130"
  },
  "trace": [
    {"paso": "suficiencia", "pregunta": "¿Información suficiente?", "resultado": "si",
     "detalle": "EDAD_CLIENTE cubre la regla"},
    {"paso": "generacion",  "accion": "Generar la consulta", "intento": 1},
    {"paso": "resultado",   "estado": "completado"}
  ]
}
```

Cuando la regla no se puede interpretar:

```json
{
  "estado": "ambigua",
  "falta": "No hay ningún campo de edad en el diccionario.",
  "trace": [{"paso": "suficiencia", "pregunta": "¿Información suficiente?", "resultado": "no",
             "detalle": "No hay ningún campo de edad en el diccionario."}]
}
```

`estado` es `completado`, `ambigua` o `error` (con `error` en vez de
`falta`). `trace` es opcional: si la mandas, la pantalla "Flujo de
validación" la pinta paso a paso; si no, esa pestaña dirá que no hay traza.

**Reglas que la consulta debe cumplir**, porque el navegador la ejecuta
contra SQLite y la rechaza si no:

- Un único `SELECT` (o `WITH … SELECT`). Nada que escriba.
- Solo campos del diccionario que recibiste.
- La tabla se llama como el campo `tabla` de la petición.
- Que devuelva una fila por registro que incumple. Un `COUNT(*)` haría
  que la pantalla dijera "1 caso detectado" siempre.

---

## 2. `POST /llm/explain` — qué tienen en común los casos

Opcional. Si no la implementas, devuelve 404 y la pantalla dirá "sin
explicación registrada".

**Petición**

```json
{
  "regla": "La edad del cliente no puede superar 130 años",
  "condicion_error": "EDAD_CLIENTE > 130",
  "columnas": ["ID_CONTRATO", "EDAD_CLIENTE"],
  "ejemplos": [{"ID_CONTRATO": "CT-000123", "EDAD_CLIENTE": "140"}],
  "n_casos": 2
}
```

**Respuesta 200**

```json
{
  "explicacion": "Los dos contratos afectados tienen edades imposibles, compatibles con un error de captura.",
  "factor_comun": "edades de tres cifras",
  "posible_causa": "error de captura o mapeo",
  "recomendacion": "validar el rango en el alta de cliente"
}
```

La pantalla muestra los cuatro campos concatenados. Con `explicacion` sola
ya vale.

---

## 3. `/revisions` — las revisiones

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/revisions` | lista todas |
| `POST` | `/revisions` | crea una |
| `GET` | `/revisions/{id}` | una |
| `PUT` | `/revisions/{id}` | actualiza estado/contadores |
| `DELETE` | `/revisions/{id}` | borra la revisión **y sus controles** |

Una revisión es este objeto (el `id` lo genera tu API si no lo mandas):

```json
{
  "revision_id": "rev_7f3a9c",
  "name": "Control Hipotecas Ibercaja – Junio 2024",
  "description": "Tabla de contratos hipotecarios…",
  "table_name": "contratos",
  "data_filename": "contratos.csv",
  "data_rows": 1240,
  "data_columns": 42,
  "dictionary_filename": "diccionario.csv",
  "dictionary_fields": 42,
  "status": "completada",
  "created_at": "2026-09-21T08:19:00Z",
  "updated_at": "2026-09-21T09:02:00Z"
}
```

`status` es `pendiente`, `en_ejecucion`, `completada` o `error`.

**Los ficheros no se suben.** El CSV y el diccionario se quedan en el
navegador: se leen, se cuentan filas y columnas, y solo viajan esos
metadatos. Consecuencia que conviene tener presente: al abrir una revisión
desde otro ordenador tendrás sus reglas y sus resultados, pero para
reejecutar habrá que volver a seleccionar el fichero.

---

## 4. `/revisions/{id}/checks` — los controles

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/revisions/{id}/checks` | los controles de esa revisión |
| `POST` | `/revisions/{id}/checks` | añade uno |
| `PUT` | `/revisions/{id}/checks/{check_id}` | actualiza (estado, comentario, resultados) |
| `DELETE` | `/revisions/{id}/checks/{check_id}` | borra uno |

```json
{
  "check_id": "chk_2b8e11",
  "revision_id": "rev_7f3a9c",
  "regla": "La edad del cliente no puede ser mayor de 130 años.",
  "descripcion": "La edad del cliente no puede superar 130 años",
  "tipo": "rango",
  "severidad": "bloqueante",
  "campos_entrada": ["EDAD_CLIENTE"],
  "condicion_error": "EDAD_CLIENTE > 130",
  "sql": "SELECT ID_CONTRATO FROM contratos WHERE EDAD_CLIENTE > 130",
  "status": "validated",
  "feedback": "Revisado con negocio el 12/09.",
  "n_casos": 2,
  "columnas": ["ID_CONTRATO"],
  "ejemplos": [{"ID_CONTRATO": "CT-000123"}],
  "explicacion": "…",
  "trace": [],
  "created_at": "2026-09-21T08:25:00Z",
  "updated_at": "2026-09-21T08:40:00Z"
}
```

`status` es `pending`, `validated` o `rejected`.

`n_casos`, `columnas` y `ejemplos` **los calcula el navegador** ejecutando
la consulta sobre el fichero; tu API solo los guarda. `ejemplos` viene
recortado a 50 filas y 8 columnas para no engordar el item.

---

## Esquema de DynamoDB

Una tabla, clave compuesta, con la fecha ordenando dentro de cada revisión:

| | Atributo | Ejemplo |
|---|---|---|
| **Partition key** | `pk` | `REV#rev_7f3a9c` |
| **Sort key** | `sk` | `2026-09-21T08:19:00Z#META` |

| Qué es | `pk` | `sk` |
|---|---|---|
| La revisión | `REV#<revision_id>` | `<created_at>#META` |
| Un control | `REV#<revision_id>` | `<created_at>#CHECK#<check_id>` |

Con esto:

- **Leer una revisión entera** (ella y sus controles) es una sola `Query`
  por `pk`, y sale ordenada por fecha.
- **Borrar una revisión** es esa misma `Query` y un `BatchWriteItem`.
- **Listar todas las revisiones** necesita un índice secundario global,
  porque la `pk` es distinta por revisión:

  | GSI `por_fecha` | Atributo |
  |---|---|
  | Partition key | `tipo` (constante `"REV"` solo en los items `#META`) |
  | Sort key | `created_at` |

  Así `GET /revisions` es una `Query` sobre el GSI ordenada por fecha
  descendente, sin escanear la tabla. Los items de control no llevan el
  atributo `tipo`, así que no aparecen en el índice: en DynamoDB un item
  sin la clave del GSI simplemente no se indexa, y eso es lo que quieres.

Modo de capacidad **on-demand**: el uso es esporádico y en reposo no paga.

---

## Errores

Cualquier respuesta que no sea 2xx se muestra al usuario tal cual. Devuelve
un cuerpo con `detail` y un mensaje que un revisor pueda entender:

```json
{"detail": "El modelo no está disponible en esta región."}
```

Si devuelves HTML o un traceback, eso es lo que verá en pantalla.

---

## Modo local (sin API)

Con `BASE_URL` vacía la app sigue siendo utilizable con **tus** ficheros:

| Funciona | No funciona |
|---|---|
| Subir tu CSV y tu diccionario | Derivar la SQL desde lenguaje natural |
| Ejecutar consultas de verdad (SQLite WASM) | Explicación automática de los casos |
| Ver casos, porcentajes y el informe | |
| Validar, rechazar, comentar | |

Sin modelo, al añadir una regla la pantalla te pide la consulta SQL: la
escribes, se ejecuta contra tu fichero y el resto del recorrido es idéntico.
Las revisiones se guardan en el navegador (`localStorage`) hasta que
configures la API.

---

## Lo mínimo para verlo funcionando

1. Una Lambda detrás de API Gateway con la ruta `POST /llm/interpret`, que
   llame a Bedrock y devuelva el JSON de arriba.
2. `BASE_URL` en `config.js`.

Con eso ya se generan controles. Las rutas de `/revisions` y `/checks`
pueden esperar: hasta que existan, el estado vive en el navegador.
