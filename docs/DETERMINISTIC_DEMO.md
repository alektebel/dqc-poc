# DQC-PoC — Deterministic Demo: how the cases go

> LLM-free walkthrough of the DQC ReAct pipeline, driven by the repo's own
> scripted backend (`demo/demo_server.py`). Every result below was produced on
> `http://localhost:8050` against the bundled fixtures — no Bedrock/Ollama, no
> network, fully reproducible. Dictionary: `demo/fixtures/diccionario_demo.xlsx`
> (sheet `DICCIONARIO`, 6 fields). Rules: `demo/reglas_demo.txt`. Cases:
> `demo/fixtures/casos_demo.xlsx` (6 rows, `DQC_ID` column).

---

## 1. Backend readiness verdict (the answer to "is it ready for AWS?")

**Code: READY.** The Bedrock backend is fully implemented in
`src/knowledge/llm_client.py` (`chat`, `chat_json_stream`, `chat_tools` →
`_chat_bedrock` / `_chat_json_stream_bedrock` / `_chat_tools_bedrock`, Converse
API), `boto3` ships in `requirements-dqc.txt` (the production image), and the
AWS/IAM wiring is already in `DQC/cdk` + `DQC/terraform`. Verified live:

```
aws sts get-caller-identity        → Account 257394490122 (authenticated)
boto3 bedrock-runtime.converse(     → HTTP 200, {"text":"OK"}
   modelId='eu.amazon.nova-micro-v1:0', region='eu-west-1')
LocalLLMClient(prefer='bedrock').detect_backend() → 'bedrock'
LocalLLMClient(...).chat([...])     → ChatResponse(backend='bedrock', text='…')
```

**Running instance: NOT wired to AWS.** The deployed Docker container runs
`REGLLM_LLM=auto` and resolves to `stub` (no Ollama sidecar, and it has no AWS
role/credentials mounted — that IAM role only exists in the ECS deploy). So the
live `:8000` stack is a demo/stub, not Bedrock. This is a *deployment-config*
gap, not a code gap.

**What "ready" still requires** (from `docs/AWS_POC_SETUP.md` / `DEPLOYMENT.md`):
enable the model under Bedrock → Model access (one-time console action); a
durable store for the checks SQLite (an ECS task replacement wipes it — EFS/RDS
is the fix); TLS/HTTPS in front of the ALB. Bedrock readiness = **yes**;
production hardening = **not yet**.

---

## 2. How the run goes (deterministic, scripted responder)

The `/dqc/generate_stream` planner splits the 7 rules into one ordered action per
line and runs each through sufficiency → generation → validation →
(semantic judge) → on failure, a bounded correction loop. Per-rule outcomes:

| # | Rule (`reglas_demo.txt`) | Attempts | Outcome | Final SQL |
|---|---|---|---|---|
| 1 | `DQC_PD_001: La PD…` | suf → gen1 → val1 → juez1 | **✓ completado** | `…WHERE PD_ESTIMADA > 1 OR PD_ESTIMADA < 0` |
| 2 | `DQC_EAD_002: El EAD…` | + gen2 → val2 → juez2 | **✓ completado (fixed)** | `…WHERE EAD_TOTAL < 0` |
| 3 | La LGD… (sin id) | + gen2 → val2 → juez2 | **✓ completado (fixed)** | `…WHERE LGD_ESTIMADA > 1 OR LGD_ESTIMADA < 0` |
| 4 | `DQC_ECL_003: El ECL…` | suf → gen1 → val1 → juez1 | **✓ completado** | `…WHERE ABS(ECL - PD*LGD*EAD) > 0.01 GROUP BY` |
| 5 | El `STAGE_IFRS9…` | gen/val ×3 | **✗ error** | (never valid — `CAMPO_FANTASMA`) |
| 6 | …colateral… | suf only | **⚠ ambigua** | (missing info) |
| 7 | …divisa… | suf only | **⚠ ambigua** | (`IMPORTE_DIVISA` hallucinated) |

**The correction loops (what the ReAct judge/model review actually exercises):**

- **Rule 2 — semantic-judge correction**: first attempt generated
  `WHERE EAD_TOTAL >= 0` (selects the *compliant* rows). The semantic judge
  rejected it — *"El sentido está invertido…"* — and the second attempt produced
  the correct `WHERE EAD_TOTAL < 0`.
- **Rule 3 — hallucinated-field correction**: first attempt used `LGD_INEXISTENTE`
  (not in the dictionary), caught statically; retried against the real field.
- **Rule 4 — execution-error correction**: first attempt appended `GROUP BY`
  causing an execution error on the cases; corrected to the reperformation check.
- **Rule 5 — exhausted attempts**: never validates after 3 tries → surfaced as an
  error with reason "No validado tras 3 intentos…".
- **Rules 6/7 — ambiguity / hallucination catch**: the model either admits the
  dictionary lacks collateral info (rule 6) or is deterministically flipped to
  ambiguous because it claimed a nonexistent `IMPORTE_DIVISA` (rule 7).

---

## 3. How the cases go (generate → evaluate against `casos_demo.xlsx`)

After generation, `/dqc/evaluate` runs each stored control's SQL against the
6-row cases workbook and reports example violating rows + precision/recall when
the control has a `prev_id` matching the cases' `DQC_ID` label. Deterministic
output from the run:

```
casos: 6 | evaluados: 3 (+1 fallido) | precision_media: 1.0 | recall_medio: 1.0
```

| check | prev_id | ok | P | R | exp | n_casos | example row |
|---|---|---|---|---:|---:|---:|---:|---|
| `PD_ESTIMADA` range | DQC_PD_001 | ✓ | 1.0 | 1.0 | 2 | 2 | `{"PD_ESTIMADA":"1.15", …}` |
| `EAD_TOTAL` ≥ 0 | DQC_EAD_002 | ✓ | 1.0 | 1.0 | 2 | 2 | `{"EAD_TOTAL":"-500", …}` |
| `LGD_ESTIMADA` range | — | ✓ | — | — | — | 1 | `{"LGD_ESTIMADA":"1.2", …}` |
| `ECL` re-perf | DQC_ECL_003 | ✗ | — | — | — | 0 | error: `incomplete input` |

Notes on the table:

- Controls #1 and #2 **fully detect** their planted cases (P=1, R=1).
- Control #3 catches its violating row but has **no historical grade** (no
  `prev_id`), so it reports P/R as `—` (this is the doc'd rule-3 behaviour).
- Control #4's `…GROUP BY` query **fails to execute** on the cases (`incomplete
  input`), so `/evaluate` marks it `ok=False`. This is faithful to the fixture:
  the cases sheet lacks the columns/grouping the query needs, mirroring the
  real-world case where a control is valid SQL for the DB but not for the
  extracted-cases workbook.

---

## 4. How to reproduce

```bash
# 1. deterministic scripted backend (fresh writable checks DB)
rm -f data/dq/checks.db        # the root-owned container DB made persistence readonly
DEMO_SLEEP=1.0 python -m uvicorn demo.demo_server:app --port 8050

# 2. streamed generation (persists the valid DQCs)
curl -N -X POST localhost:8050/dqc/generate_stream \
  -F dictionary=@demo/fixtures/diccionario_demo.xlsx \
  -F instructions_file=@demo/reglas_demo.txt \
  -F table_name=mylib.ciclos_recuperacion \
  -F value_grounding=true -F semantic_judge=true

# 3. evaluate the controls against the cases
curl -X POST localhost:8050/dqc/evaluate \
  -F data_file=@demo/fixtures/casos_demo.xlsx \
  -F table_name=mylib.ciclos_recuperacion
```

Live at `http://localhost:8050` (`/health` → `{"status":"ok","llm_backend":"stub"}`),
started from `demo/demo_server.py`, which swaps in `DemoLLM` and reuses the real
`api.main` app + ReAct pipeline.

---

## 5. Findings worth flagging

1. **Root-owned `data/dq/checks.db` silently broke persistence.** The
   container-mounted volume left a root-owned SQLite file; any non-root writer
   (the demo server, a local `uvicorn`) logged `persist failed: attempt to write a
   readonly database` and `/evaluate` returned 0. Removed it; a fresh writable DB
   is now created on demand. Mitigate: run the container as a non-root user and/or
   mount a writable volume, and gate on migration rather than a stale file.
2. **`/dqc/generate` (buffered) yields 0 DQCs**; the deterministic showcase is the
   **`/generate_stream` ReAct path** whose system prompts the `DemoLLM` responder
   is keyed on. Documented in `demo/README.md` — the buffered endpoint is fine
   against a real LLM but is not the demo target.
3. **Rule 4's `GROUP BY`** is a faithful fixture of the execution-error branch, and
   it legitimately fails on the cases workbook — expected, not a bug.