# Data Quality Assistant — PoC

Genera controles de calidad de datos (consultas SQL) a partir de **una tabla
+ su diccionario de campos + reglas en lenguaje natural**, los ejecuta sobre
los datos subidos y deja que un revisor valide o rechace cada uno.

Es una única aplicación: FastAPI sirve la API **y** las cuatro pantallas,
así que se arranca un proceso y se abre un puerto.

## Las cuatro pantallas

| Pantalla | Fichero | Qué hace |
|---|---|---|
| Listado | `web/home.html` | revisiones existentes, su estado y la última ejecución |
| Paso 1 | `web/index.html` | nombre, descripción de la tabla (≥100 caracteres) y el fichero de datos (.csv/.xlsx) |
| Paso 2 | `web/dictionary.html` | el diccionario que explica esas columnas (.csv/.xlsx) |
| Paso 3 | `web/rules.html` | reglas en lenguaje natural, su interpretación, los casos detectados y el informe |

**Las cuatro páginas son las maquetas tal y como se entregaron**, byte a byte,
con una sola línea añadida antes de `</body>`:

```html
<script src="assets/app.js"></script>
```

Todo lo demás —llamadas a la API, el contenido real que sustituye a las filas
de ejemplo, los dos controles que el diseño no traía (validar/rechazar) y el
modal del informe— vive en `web/assets/app.js`. Cada maqueta trae su propio
script de demostración, que se ejecuta antes; `app.js` lo desactiva
reemplazando los nodos por clones sin listeners, en vez de editar el diseño.

Consecuencia de no tocar el HTML: **los textos de la maqueta se mantienen
aunque los datos sean reales** — "Interpretación (ejemplo)", "Resultados
(ejemplo)", "CSV cargado" en la cabecera. Se cambian editando la maqueta,
cuando quieras. Y `pwc-logo.png`, que la maqueta referencia y este repo no
incluye: deja el tuyo en `web/` y aparece; mientras tanto `app.js` lo oculta.

Una **revisión** agrupa la tabla, su diccionario y los controles generados
sobre ella. Cada control queda ligado a su revisión, de modo que el informe
de una revisión nunca mezcla controles de otra.

## Arrancar

```bash
pip install -r requirements.txt
uvicorn api.main:app --port 8000 --reload
```

Abre **http://localhost:8000**.

Con Docker:

```bash
cp .env.example .env
docker compose up --build            # http://localhost:8000
```

Sin modelo configurado el backend cae a modo **stub**: la aplicación
funciona (se crean revisiones, se navegan las pantallas) pero los controles
generados son marcadores de posición. Para generación real:

- **Ollama local**: `docker compose --profile ollama up --build`
  (descarga `${OLLAMA_MODEL}`, por defecto `qwen3:4b`), o
- **Amazon Bedrock**: `REGLLM_LLM=bedrock uvicorn api.main:app --port 8000`
  — credenciales por la cadena estándar de boto3. `BEDROCK_MODEL_ID` debe ser
  un *inference profile* (`eu.amazon.nova-micro-v1:0`); el id desnudo se
  rechaza para on-demand.
- `REGLLM_LLM=auto` prueba litert, ollama y gguf, luego Bedrock si hay
  credenciales, y solo entonces el stub.

`python scripts/diagnose_llm_backend.py` dice qué backend está activo y por
qué, desde el mismo intérprete que usa la aplicación.

## Cómo funciona una regla

Al añadir una regla se ejecuta el mismo bucle de agente que el generador por
lotes, con contexto fresco en cada paso:

1. **Suficiencia** — ¿hay campos suficientes en el diccionario para este
   control? Si no, la regla se marca ambigua y se dice qué falta.
2. **Generación** — se deriva la consulta usando solo campos del diccionario.
3. **Validación** — estática (los campos existen) y dinámica (la consulta se
   ejecuta contra la tabla subida, en SQLite en memoria).
4. **Corrección** — un error de validación vuelve al generador como
   feedback, hasta 3 intentos.
5. **Atribución** — qué campos lee realmente la consulta, contrastado con los
   que el modelo dice usar (un campo declarado y no usado delata una
   justificación inventada).
6. **Explicación** — qué tienen en común los casos detectados.

Esa traza es lo que muestra la pestaña **Flujo de validación**: es el
registro real de la ejecución, no una ilustración.

### Dónde se ejecuta el control

El agente deriva la consulta; ejecutarla es de `api/dq/executor.py`, y
quién lo hace se elige por inyección:

| Ejecutor | Dónde corre la consulta |
|---|---|
| `UploadedTableExecutor` | el fichero subido, en SQLite en memoria |
| `DatabaseExecutor` | cualquier conexión DB-API 2.0 (cx_Oracle, pyodbc, psycopg2, snowflake): la consulta va a donde ya están los datos y solo vuelven los recuentos y una muestra |

La consulta la escribe un modelo, así que **el modo solo-lectura se
comprueba, no se supone**: `assert_read_only` rechaza cualquier cosa que
no sea un único SELECT antes de que la conexión la vea. Es la segunda
línea de defensa; la primera son credenciales de solo lectura.

### Lotes

Un fichero de reglas es un **job**: `POST .../rules/batch` responde al
instante con un `job_id` y el trabajo ocurre fuera de la petición, un
worker por regla (`REGLLM_JOB_WORKERS`, por defecto 4), cada uno con su
propio acceso a los datos. La pantalla hace *polling* de
`GET .../jobs/{job_id}`, que devuelve una fila por regla.

Que cada regla sea una unidad aislada es lo que permite trocearla: en
local es un hilo; en AWS sería una invocación de Lambda. Ver
[`docs/AWS_ARCHITECTURE.md`](docs/AWS_ARCHITECTURE.md).

El botón **Reejecutar** de un control vuelve a derivar la consulta pasando
al generador el motivo que escribe el revisor, y la reejecuta. El control
conserva su id y su historial: es la misma regla, reinterpretada.

## API

Todo bajo `/dqc`. Las pantallas no usan ningún otro origen.

| Método y ruta | Para qué |
|---|---|
| `POST /dqc/revisions` | crear revisión (nombre, descripción, fichero de datos) |
| `GET /dqc/revisions` | listado |
| `GET/DELETE /dqc/revisions/{id}` | detalle / borrar (con sus controles y ficheros) |
| `POST /dqc/revisions/{id}/dictionary` | subir el diccionario |
| `GET /dqc/revisions/{id}/rules` | reglas de la revisión con sus últimos casos |
| `POST /dqc/revisions/{id}/rules/preview` | interpretar una regla sin guardarla |
| `POST /dqc/revisions/{id}/rules` | guardar la interpretación revisada |
| `POST /dqc/revisions/{id}/rules/batch` | encola un fichero de reglas como job (202) |
| `GET /dqc/revisions/{id}/jobs/{job_id}` | estado del job, una fila por regla |
| `GET /dqc/revisions/{id}/jobs` | último job de la revisión |
| `POST /dqc/revisions/{id}/rules/{cid}/rerun` | reejecutar con un motivo |
| `GET /dqc/revisions/{id}/report` | informe: validadas + consulta centralizada |
| `POST /dqc/checks/{id}/status` | validar / rechazar |
| `POST /dqc/checks/{id}/feedback` | comentario de revisión |
| `DELETE /dqc/checks/{id}` | borrar un control |
| `GET /health` | estado + backend LLM activo |

El generador por lotes original (`POST /dqc/generate`,
`/dqc/generate_stream`, `/dqc/evaluate`, `/dqc/dashboard`) sigue disponible
para uso sin revisiones. Documentación interactiva en `/docs`.

### Ficheros de entrada

`.csv` y `.xlsx`, tanto para la tabla como para el diccionario. El lector
decide por el contenido (un `.xlsx` es un zip), así que un fichero mal
nombrado se lee igual; uno que dice ser Excel y no lo es se rechaza en vez de
interpretarse como texto. En un CSV los números se convierten a número: sin
eso, SQLite compararía texto contra número y un control de rango marcaría
todas las filas.

## Estructura

```
api/
  dq/pipeline.py         el bucle de agente, sin FastAPI ni persistencia
  dq/worker.py           una regla → un resultado JSON (la unidad de trabajo)
  dq/executor.py         dónde se ejecuta el control (fichero | BBDD)
  routers/dqc.py         generador por lotes, checks CRUD
  routers/revisions.py   revisiones, jobs y el flujo de las pantallas
  routers/tabular.py     lector único .csv/.xlsx
web/            las cuatro maquetas, intactas + assets/app.js (todo el cableado)
src/knowledge/  cliente LLM multi-backend, BCBS 239, atribución
training/dq/    persistencia SQLite (controles, revisiones y jobs)
DQC/eval/       harness de evaluación del agente (mutation testing)
data/samples/   diccionario y casos de ejemplo
tests/          suite completa (pytest)
```

## Estado en disco

Todo vive bajo `data/` y se monta como volumen en Docker:

- `data/dq/checks.db` — revisiones y controles (SQLite).
- `data/revisions/<id>/` — la tabla y el diccionario subidos en esa revisión.

Variables: `REGLLM_CHECKS_DB`, `REGLLM_REVISIONS_DIR`, `REGLLM_JOB_WORKERS`.

## Tests

```bash
pytest -q
python -m pyflakes api/ src/ training/ scripts/ tests/    # el CI lo exige en cero
```

## Automatización

`.github/workflows/ci.yml` se ejecuta en cada push y pull request:

1. **Tests y lint** — instala, pasa `pyflakes` y la suite completa.
2. **Imagen** — construye el `Dockerfile`, **arranca el contenedor en el
   propio runner** y lo verifica con `scripts/smoke.py`. Solo si eso pasa,
   publica en GHCR.

La verificación no es un health check: crea una revisión desde un CSV,
sube el diccionario, lee las reglas, genera el informe y borra lo que ha
creado, además de pedir las cuatro pantallas y sus assets. Una imagen que
arranca pero se dejó `web/` fuera responde `/health` y falla aquí.

Sirve igual contra cualquier despliegue, no solo en CI:

```bash
python scripts/smoke.py --base-url http://localhost:8000
```

Sale con código 0 o 1, así que encadena bien en cualquier script.

**Dónde acaba la imagen**: `ghcr.io/<owner>/dqc-poc`, etiquetada por commit
(`sha-abc1234`), por rama y por versión (`v1.2.3` desde una etiqueta git).
Se publica **solo desde `main` y desde etiquetas `v*`**: una rama de
trabajo se construye y se verifica, pero no deja imagen en el registro.
Nada se despliega en ningún sitio: el workflow produce un artefacto, no
un entorno.

## Harness de evaluación

```bash
python DQC/eval/eval_harness.py --selftest
python DQC/eval/eval_harness.py --agent http://localhost:8000
python DQC/eval/coverage_matrix.py --fail-under 1.0
```

Ver [`DQC/eval/README.md`](DQC/eval/README.md) y
[`docs/EVALUATION.md`](docs/EVALUATION.md).

## Docs

- [`docs/REACT_PIPELINE.md`](docs/REACT_PIPELINE.md) — diseño del bucle de agente
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — cómo se mide el agente
- [`docs/EVAL_ROADMAP.md`](docs/EVAL_ROADMAP.md) — qué no mide todavía
- [`docs/AWS_ARCHITECTURE.md`](docs/AWS_ARCHITECTURE.md) — qué construiríamos en AWS, con costes y límites
