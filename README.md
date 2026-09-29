# DQC benchmark — PD/LGD

Benchmark para evaluar herramientas de generación de controles de calidad de
datos (DQC) sobre una base de reporting de PD/LGD, con errores sembrados según
las directrices de la EBA sobre estimación de PD y LGD (EBA/GL/2017/16).

El repositorio contiene dos piezas:

| Pieza | Dónde | Estado |
|---|---|---|
| RAG de las directrices | `src/knowledge/`, `scripts/`, `data/regulation/` | funcional |
| Benchmark | `benchmark/` | diseño; ver [`benchmark/README.md`](benchmark/README.md) |

## Instalación

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # elige el backend de embeddings
pytest
```

## RAG de las directrices

```
PDF ──ingest_pdf.py──► data/regulation/<doc>.json   (un registro por párrafo numerado)
                              │
               build_regulation_embeddings.py        (chunking + embeddings)
                              │
              data/regulation/embeddings/pd_lgd_chunks.json
                              │
                   search_regulation.py "consulta"   (similitud coseno, cita §N)
```

```bash
# 1. PDF → JSON de párrafos (ya incluido para EBA/GL/2017/16: 221 párrafos)
python scripts/ingest_pdf.py GL_2017_16_ES.pdf --out data/regulation/eba_gl_2017_16_articles.json

# 2. Índice de embeddings (requiere Ollama, GGUF o Bedrock; ver .env.example)
python scripts/build_regulation_embeddings.py

# 3. Consulta
python scripts/search_regulation.py "margen de cautela en la calibración de la LGD" -k 5
```

- **Chunking** (`regulation_chunker.py`): un chunk por párrafo; los párrafos
  largos se parten en ventanas solapadas alineadas a frase. Nunca se fusionan
  párrafos, así que cada resultado se puede citar como `EBA GL 2017/16 §N`.
- **Vector store** (`regulation_vector_store.py`): coseno en Python puro,
  persistido en un JSON con manifiesto (backend, modelo, dimensión).
- **Embeddings** (`embeddings.py`): Ollama, GGUF (llama-cpp), Bedrock Titan o
  `stub`. Con `stub` el índice se construye pero **no ordena nada** (vectores
  a cero): sirve para tests, no para recuperar.
- **Ingesta de PDF** (`ingest_pdf.py`): heurística para el formato EBA
  (párrafos `N.` en secuencia, encabezados `4.2.1 Título`). La extracción
  de texto de un PDF pierde información: revisa la lista de secciones y los
  primeros y últimos párrafos antes de indexar.

Limitación conocida del JSON incluido: algunos títulos de sección están
truncados (p. ej. `"1 Obligaciones de cumplimiento y de"`) por encabezados que
ocupaban dos líneas en el PDF original. `ingest_pdf.py` une esas líneas; al
regenerar el JSON desde el PDF se corrige.
