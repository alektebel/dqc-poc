# DQC PoC — Studio de generación de controles

A standalone Data-Quality-Check generator PoC for regulatory data pipelines
(IRB / IFRS 9). It generates structured data-quality checks (SQL) from an
**Excel field dictionary + natural-language instructions**, and lets a
reviewer validate or reject each one — all through a **Modernist**-styled
single-page app.

This repo is a self-contained slice of the larger RegLLM work. It ships:

| Piece | Where | Role |
|---|---|---|
| DQC generator API | `api/` (FastAPI) | `/dqc/*` endpoints: dictionary inspection, generation (buffered + SSE), cases evaluation, checks CRUD, dashboard |
| Validation store | `training/dq/` | SQLite persistence for generated checks (statuses, dashboard UNION ALL) |
| RAG / LLM client | `src/knowledge/` | multi-backend LLM client (Ollama / LiteRT / GGUF / Bedrock / stub) + regulation knowledge graph + change-log GraphRAG |
| **DQC Studio UI** | `DQC/studio/` | Modernist single-page app (Proyectos → Generar → Revisar) wired to the API |
| Eval harness | `DQC/eval/` | mutation-testing certifier for the DQC agent (selftest / coverage / agent scoring) |
| Cloud infra | `DQC/cdk`, `DQC/terraform`, `DQC/azure`, `DQC/lambda` | AWS (CDK + Terraform + Lambda) and Azure deployment assets |
| Angular UI | `DQC/app/` | the earlier chat-based UI (kept for reference) |
| Demo kit | `demo/` | scripted LLM-free demo of every pipeline branch + demo dictionary/cases Excel |

The **style** follows the Modernist design system from the `PwC color
palette webapp (1).zip` left in this repo (now extracted under
`DQC/studio/assets/`): flat, Archivo, a near-mono red on white, visible
modular grid, zero corner radius, strong 2px rules.

---

## Quickstart (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Open **http://localhost:4200** for the DQC Studio. The API runs on
`http://localhost:8000` (health: `GET /api/health`).

With no LLM configured the backend falls back to **stub** mode — the app
still loads (and you can open a project, browse checks, and review/validate
the seeded demo controls). For real generation, either:

- add a local **Ollama** model: `docker compose --profile ollama up --build`
  (pulls `${OLLAMA_MODEL}`, default `qwen3:4b`), or
- point `REGLLM_LLM=bedrock` at Amazon Bedrock / Nova (see
  [`docs/AWS_POC_SETUP.md`](docs/AWS_POC_SETUP.md)):

  ```bash
  REGLLM_LLM=bedrock docker compose up -d api      # Docker
  REGLLM_LLM=bedrock uvicorn api.main:app --port 8000 --reload   # no Docker
  ```

  `curl localhost:8000/health` should then report `"llm_backend":"bedrock"`.
  If it does not, run the diagnostic **from the failing environment**, using the
  same interpreter the app uses:

  ```bash
  .venv/bin/python scripts/check_aws.py        # or
  docker exec dqc-poc-api python scripts/check_aws.py
  ```

  It names the credential source, separates a disabled region from a bad
  credential, and ends with a real Nova call. A venv never changes which
  credentials boto3 finds — it shares the CLI's chain (env vars → `~/.aws` →
  SSO cache → IMDS), so CLI/app disagreements are always environmental.
  `REGLLM_LLM=auto` also reaches Nova now: it probes litert, ollama and gguf,
  then Bedrock when AWS credentials resolve, and only stubs if nothing answers.
  Setting it explicitly is still clearer, and is what the Docker default does
  (compose ships `REGLLM_LLM=api`; put `REGLLM_LLM=bedrock` in `.env` to make
  Nova the default for `docker compose up`). Defaults
  are `eu.amazon.nova-micro-v1:0` in `eu-west-1`; that id is an *inference
  profile*, and the bare `amazon.nova-micro-v1:0` is rejected for on-demand
  throughput. Credentials come from the usual boto3 chain — compose mounts
  `~/.aws` read-only and forwards `AWS_PROFILE` / `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` when set.

To showcase the full workflow without any model, open the UI with
`?demo=1` (client-side seed, no API needed).

## Run locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# backend (stub LLM by default; use REGLLM_LLM=ollama / bedrock for real gen)
uvicorn api.main:app --port 8000 --reload

# frontend — static Studio, /api proxied to :8000
python scripts/serve_studio.py --port 4200
```

Open http://localhost:4200.

## The DQC Studio flow

1. **Proyectos** — a project groups a field dictionary, its input sources and
   the generated controls. Create one (or open an existing).
2. **Generar** — write one natural-language rule per line (or upload a test
   list), attach the field dictionary Excel (`.xlsx`), and generate. The
   assistant builds a plan, runs each rule through sufficiency → SQL
   generation → validation → (optional) semantic-judge, and streams the
   reasoning live. With a data-cases Excel attached, example violating rows
   and precision/recall come back per control.
3. **Revisar** — review each generated control one at a time: how it was
   decided, its SQL, and the cases it detects. Validate or reject.
4. **Resumen** — the control totals, a status bar, the full control list, and
   a **centralised query** that folds every validated control into one
   `UNION ALL` rowset (downloadable `.sql`).

## API surface (`/api/dqc/*`)

| Endpoint | Description |
|---|---|
| `POST /dqc/inspect_dictionary` | inspect an uploaded workbook: propose the dictionary sheet + column mapping |
| `POST /dqc/generate` | buffered generation from a dictionary + NL instructions |
| `POST /dqc/generate_stream` | plan-mode generation, streamed over SSE (`meta`/`plan`/`item`/`done`) |
| `POST /dqc/evaluate` | run the stored checks against a data-cases Excel |
| `GET  /dqc/checks` | list checks (filter by `status`, `project_id`) |
| `GET  /dqc/checks/counts` | counts by status × visibility |
| `POST /dqc/checks/{id}/status` | validate / reject a check |
| `GET  /dqc/checks/{id}/cases` | latest detected-cases payload for a check |
| `DELETE /dqc/checks/{id}` | delete a check |
| `GET  /dqc/dashboard` | validated checks + the centralised query |

## Eval harness (certify the agent)

```bash
python DQC/eval/eval_harness.py --selftest
python DQC/eval/eval_harness.py --sql DQC/eval/example_checks.sql
python DQC/eval/eval_harness.py --agent http://localhost:8000/api
python DQC/eval/coverage_matrix.py --fail-under 1.0
```

See [`DQC/eval/README.md`](DQC/eval/README.md).

## Tests

```bash
pytest -q
```

## Structure

```
api/            FastAPI app + /dqc routers
src/knowledge/  LLM client + regulation RAG + GraphRAG
training/dq/    SQLite checks store
DQC/studio/     Modernist DQC Studio (static SPA + nginx Dockerfile)
DQC/app/        earlier Angular chat UI (reference)
DQC/eval/       mutation-testing eval harness
DQC/cdk|terraform|azure|lambda/   deployment assets
demo/           scripted demo (LLM-free) + fixtures
data/           regulation corpus, docs, demo dictionary/cases
docs/           PoC setup, deployment, evaluation, regulation-RAG guides
scripts/        run_local.sh, serve_studio.py, embed/LLM helpers
```

## Docs

- [`docs/AWS_POC_SETUP.md`](docs/AWS_POC_SETUP.md) — deploy to AWS (CDK)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — slim-image strategy + Azure mirror
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — how the agent is measured
- [`docs/REGULATION_RAG.md`](docs/REGULATION_RAG.md) — the two RAG channels
- [`docs/REACT_PIPELINE.md`](docs/REACT_PIPELINE.md) — the agent pipeline design
