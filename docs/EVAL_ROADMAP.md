# DQC Eval — gaps and next techniques

Companion to [`EVALUATION.md`](EVALUATION.md) and
[`DQC/eval/README.md`](../DQC/eval/README.md). Those describe the harness that
**exists**. This describes what it does not measure yet, why each gap matters,
and how to close it.

Read the existing harness first. It is more complete than most LLM evals: 67
ground-truth defects with executable oracles, k-row mutation traps, a mixed DB
with all defects planted at once, overbroad-check detection, decoys, 16 golden
traces and a `--fail-under` CI gate.

---

## What is already covered (do not rebuild)

| Technique | Where | Notes |
|---|---|---|
| **Execution equivalence** | `eval_harness.py`, `defect_catalog.py` | Every defect carries an `oracle_sql` and a `mutate(row)`. Candidate checks are scored on whether they fire on planted rows, **not** on SQL text similarity. This is the right design and it is already built. |
| **Precision / recall on labelled rows** | `dqc_react.metrics()`, `eval_harness.py` | `r_catches` is the *fraction* of k planted rows caught, so memorising one row no longer scores full recall. The live path also computes `precision_media` / `recall_medio` into `evaluacion`. |
| **Mutation testing** | `generate_db.py` (`TRAP_K = 3`) | Each planted row derives from a different random base, sampling the violation space at k points. |
| **Reward-hacking detection** | mixed-DB confusion matrix | A check firing on >3 distinct defects is flagged *overbroad*; checks fishing for trap PKs are caught the same way. |
| **Hand-crafted golden dataset** | `golden_traces.json`, `golden_eval.py` | 16 traces over 8 dimensions, including 2 adversarial. `--selftest` proves gold answers score 100%. |
| **Regression gate** | `--fail-under` | Per-dimension and per-article recall. |

So of the three you proposed — SQL correctness, LLM-as-judge rubric, golden
dataset — **two are done**. The judge is the open one, and it is open in a
more uncomfortable way than it looks.

---

## Gap 1 — the LLM judge ships unevaluated

`eval_harness.py` states its modes are *"all program-executed, no LLM judge"*,
and `EVALUATION.md` presents needing no LLM judge as a strength. For scoring
against oracles, that is correct.

But the **product** runs an LLM judge. `dqc_react.judge_dqc()` gates generated
checks when `semantic_judge` is on, and its verdict feeds the correction loop.
That judge has no measurement at all. The harness's independence from LLM
judging is exactly why the judge in the pipeline is invisible to it.

Worse, it fails open — from its own docstring:

> *A failure to judge accepts the query — the judge only ever adds scrutiny.*

A judge that errors, times out, or returns unparseable JSON silently approves.
Today you cannot distinguish "the judge approved" from "the judge never ran".

**Close it with:**

1. **A judge-calibration set.** 50–100 `(rule, SQL, verdict)` triples labelled
   by a human who did not write the prompts. Score the judge against them with
   **Cohen's κ**, not raw accuracy — raw accuracy flatters a judge that always
   says "correct" on a set that is mostly correct.
2. **Separate the failure modes.** Emit `judge_ok`, `judge_failed` and
   `judge_skipped` distinctly instead of collapsing all three into acceptance.
   The trace already carries a `juicio` step; it just needs the third state.
3. **Free labels.** The oracles are ground truth. Run the judge over checks
   whose correctness the harness already knows and measure agreement. This
   needs no new labelling and can run in CI today.

---

## Gap 2 — position and verbosity bias (what you asked about)

These are two well-documented systematic biases in LLM-as-judge setups. They
matter because a biased judge does not add noise — it adds a *consistent* tilt
your metric will happily report as signal.

### Position bias

When a judge compares two candidates, it favours one **slot** regardless of
content. Published results show strong judges flipping their verdict on a large
share of pairs purely from swapping A and B.

**Test:** score every pair twice, A/B then B/A.

```
agreement = (# pairs where the verdict survives the swap) / (# pairs)
```

Below ~0.9 the comparison is measuring position, not quality. Fixes: average
over both orders, or avoid pairwise comparison entirely.

Note this applies to *pairwise* judging. `judge_dqc` is currently **pointwise**
— one query, one verdict — so it is not exposed today. It becomes relevant the
moment you compare two candidate SQLs, which is the obvious next step for the
correction loop, and it is why you should not build that comparison naively.

### Verbosity bias

Judges systematically prefer longer answers, independent of correctness. A
generator that emits a verbose `descripcion` and heavily commented SQL scores
better than a terse, equally correct one. Over a few prompt iterations you are
no longer optimising correctness — you are optimising length, and your eval is
rewarding it.

**Test:** take pairs the judge already rated equal, pad one side with a comment
block or a restated description that adds no logic, re-judge.

```
verbosity_delta = P(judge prefers padded) - 0.5
```

Anything meaningfully above 0 means length is leaking into the score. Fixes:
put an explicit "length is not quality" clause in the rubric, strip comments
before judging, or include token count as a covariate so you can see whether a
score gain is just a length gain.

Both are cheap to run and belong next to the calibration set, because they
tell you whether that set's numbers mean anything.

---

## Gap 3 — retry efficiency (nothing measures it)

`MAX_ATTEMPTS = 3`. The generation loop is generate → validate → correct, and
the decision trace already records `{"paso": "generacion", "intento": n}` for
each round. **No eval reads it.** Pass rate alone cannot distinguish a model
that succeeds first try from one that needs three — same score, 3× the cost and
latency.

Measure, per rule:

| Metric | Why |
|---|---|
| `attempts_to_success` distribution | The headline. Report the histogram, not the mean — the mean hides a bimodal "instant or never". |
| `first_attempt_pass_rate` | The cleanest signal of generation-prompt quality. A prompt change should move this. |
| `exhaustion_rate` | Fraction hitting `MAX_ATTEMPTS` and failing. These are the rules to read by hand. |
| `correction_lift` | `pass@3 − pass@1`. If near zero, the correction loop is not working and the retries are pure cost. |
| **Failure taxonomy** | Group `last_errors` by cause — unknown column, syntax, empty result, judge rejection. Tells you *which* prompt to fix, not just that one is weak. |

`correction_lift` is the one to watch. A high pass rate with near-zero lift
means the retries are burning tokens to re-roll the dice rather than acting on
the feedback — a different and more fixable problem than a weak first shot.

All of this is derivable from traces the system already produces, so it is
instrumentation, not new evaluation machinery.

---

## Gap 4 — determinism (you cannot guarantee it; measure it instead)

Be precise about what is achievable, because the honest answer shapes the
BCBS 239 story.

**What you can control:** `temperature` defaults to `0.1` in `chat_json`, not
`0`. Set it to `0` for eval runs.

**What you cannot:** the Bedrock Converse API exposes `temperature`, `topP` and
`maxTokens` — **no seed**. Even at temperature 0, greedy decoding is not
bit-reproducible in practice: floating-point non-associativity across batched
GPU kernels means identical inputs can diverge, and a single differing token
early can cascade into a different query. Provider-side model updates behind a
stable model id move the target again.

So: **determinism cannot be guaranteed through the API.** What you can do:

1. **Temperature 0 for all eval runs** — removes the sampling contribution,
   which is the largest one.
2. **Pin an inference profile**, and record the exact `modelId` in every
   result. Treat a provider model update as a version bump that invalidates
   baselines.
3. **Measure variance instead of assuming it away.** Run each golden trace
   N=5 times and report:
   - `pass_rate_variance` across runs;
   - `flaky_rate` — traces that both pass and fail across the N runs.

   A flaky trace is not a passing trace. Gate CI on the *worst* run, not the
   mean, or you will ship a regression that happened to roll well.
4. **Cache by content hash** (`(prompt, model, temperature)` → response) so a
   re-run of an unchanged eval is genuinely identical and cheap. This gives
   reproducible *reports* even though the underlying model is not reproducible.
5. **Where the answer must be stable, make it not-a-model-call.** The existing
   oracles are deterministic by construction. That is the real lesson: the
   deterministic core should stay program-executed, with the LLM confined to
   the parts where variance is acceptable and measured.

For an audit conversation, "we measure and bound run-to-run variance, and gate
on the worst case" is defensible. "It is deterministic" is not, and would not
survive scrutiny.

---

## Interpretability — what was this SQL based on?

Two mechanisms, because they answer different questions at wildly different
cost. Both live in [`src/knowledge/attribution.py`](../src/knowledge/attribution.py).

### Structural attribution — free, exact, always on

Generated DQCs are SQL, and SQL *names* what it reads. Parsing the identifiers
out of the query and matching them against the dictionary fields that were in
the prompt tells you with certainty which fields the query used — and, through
each field's `reg_ref` in `data_dictionary.md`, which PD/LGD paragraph stands
behind it.

No model call, no surrogate, no guessing. It runs on every generated check and
appears as an `atribucion` step in the decision trace and an **"En qué se
basa"** panel in the review UI:

```
PD_FINAL   LGD_FINAL   EAD_TOTAL   ECL
CRR Art. 158    BCBS 239 P3
```

Identifier extraction excludes SQL keywords, string literals and comments, so a
column named only inside `-- a comment` is correctly *not* attributed.

### Counterfactual attribution — expensive, on demand

Structural attribution cannot explain context that shaped the query without
being named in it: a description that fixed a threshold, a formula that
determined a join, a guideline paragraph that motivated the rule at all. For
those, remove one context unit, regenerate, and measure how far the SQL moved.

```bash
python scripts/attribute_dqc.py --rule "La PD estimada no puede ser negativa" \
    --dictionary DQC/eval/data_dictionary.md --max-units 8 --regulation
```

**Why not ContextCite as published.** ContextCite (Cohen-Wang et al., 2024)
fits a sparse linear surrogate on the *log-probability* of the response under
randomly ablated context subsets. The Bedrock Runtime API exposes no
logprobs — `ConverseResponse` carries only `output`, `stopReason`, `usage`,
`metrics` and `trace`, and `InferenceConfiguration` only `maxTokens`,
`temperature`, `topP` and `stopSequences` — so that signal does not exist
against Nova. (The same check is why the determinism section above says a seed
is unavailable.)

The substitution: ablate one *meaningful* unit at a time rather than random
subsets, and score by output distance instead of logprob shift. Leave-one-out
over n units costs n calls instead of ContextCite's 32–64 samples, needs no
surrogate, and yields a direct counterfactual — "the SQL changes when this
field is removed" — rather than a regression coefficient.

What it gives up is **interaction effects**: two units that each cover for the
other both score 0 even though one is required. Rather than report a confident
zero, `attribute_by_ablation` flags any unit the query *names* whose removal
changed nothing as `suspected_redundancy`.

Similarity is Jaccard over identifier sets, so reformatting, re-aliasing and
comment churn do not register as semantic change.

### Surrogate attribution — ContextCite proper, where logprobs exist

There is no need to *train* anything. ContextCite's "surrogate" is a sparse
linear regression fit **per query** on ~32 ablation samples, thrown away
afterwards — not a model you train on the guidelines. What it needs is the
log-probability of a *fixed* response under ablated contexts, and that turns
out to be available:

| Backend | Teacher-forced logprobs? |
|---|---|
| Bedrock / Nova | **No.** `ConverseResponse` has no logprob field at all. |
| OpenAI-compatible (`REGLLM_API_URL`) | **Yes** — `/v1/completions` with `echo=true` returns `prompt_logprobs`. Verified against `api.nan.builders` (qwen3.6). |
| Local GGUF (`GGUF_MODEL_PATH`) | **Yes** — llama-cpp-python exposes logprobs, no per-call cost, no rate limit. |

So interpretability does not require changing the production backend: generate
with Nova, attribute with a scorer that can return logprobs
(`src/knowledge/logprob_scoring.py`). The caveat is that the attribution then
describes *that* model's dependence on the context — to make claims about the
deployed model, generate and score with the same one.

`attribute_by_surrogate` samples random context subsets, scores the fixed
response under each, and fits an L1 regression whose coefficients are the
attributions. L1 rather than ridge because attribution should be sparse: most
units genuinely contribute nothing, and ridge smears small weights across all
of them. The fit is `fit_lasso`, ~60 lines of coordinate descent in pure
Python — numpy and scikit-learn are not dependencies of this project and the
problem is tens of samples by tens of features.

Two advantages over leave-one-out ablation:

- **Cost is fixed by `n_samples`, not by context size.** 32 calls covers all 73
  dictionary fields, where ablation needs 73. The gap widens with the
  dictionary.
- **It sees interactions.** Random subsets expose units that only matter
  together, which leave-one-out reports as two confident zeros.

A negative coefficient means the unit made the response *less* likely — context
that argued against what was generated, which is worth surfacing on its own.

### A domain-specialised model is a separate, also-valid idea

Fine-tuning a credit-risk/SQL model is orthogonal to attribution and is already
scoped in [`POST_TRAINING_ROADMAP.md`](POST_TRAINING_ROADMAP.md). It would help
generation quality, and a local model would make surrogate attribution free
rather than metered — but it is not what "surrogate" means in ContextCite, and
neither depends on the other.

### Attributing the rule itself to the guidelines

`units_from_reg_chunks` makes EBA GL/2017/16 paragraphs ablatable alongside
dictionary fields. The same mechanism then answers a different question: not
"which column did this query read" but **"which paragraph of the PD/LGD
guidelines is this rule standing on"** — with `RegChunk.citation()` giving the
reference to show a reviewer. That is the honest version of the proposal
feature in §5.8: a proposed rule arrives with the paragraph whose removal
would have changed it, not with a citation the model asserted.

---

## Gap 6 — schema-linking recall (measured: **0.938**, and it is a ceiling)

`select_relevant_fields` is a tier-1 filter: it ranks the dictionary against
the rule and sends only the top slice. Right design, but it creates a silent,
unrecoverable failure — if a field the correct SQL must reference is cut before
generation, no prompt change, retry or judge downstream can bring it back.

[`DQC/eval/schema_linking.py`](../DQC/eval/schema_linking.py) measures it
against the golden traces. On the current defaults it is **not 1.0**:

| `cap` | `drop_least` | fields sent | micro recall | incomplete traces |
|---|---|---|---|---|
| **60 (current)** | **10 (current)** | **60 / 73** | **0.938** | **5 of 19** |
| 73 | 10 | 63 / 73 | 0.958 | 3 |
| 73 | 0 | 73 / 73 | **1.000** | 0 |

G07 loses `ESTADO_CICLO`; G12 loses `COSTE_TOTAL_ACUMULADO` and
`RECUPERACION_ACUMULADA`; G13 `CURE_FLAG`; G14 `RECUPERACION_ACUMULADA`;
G20 `ADJUDICACION_FLAG`. Those five traces cannot score full marks on any
downstream metric, and nothing in the harness was reporting why.

The binding constraint is `MAX_FIELDS_PER_CALL = 60`, not `DROP_LEAST_FIELDS` —
recall is flat across every `drop_least` from 10 down to 0, because the cap
wins first. On a 73-field dictionary the filter is trimming 13 fields to save
very little and costing 6% of required fields. It should engage only when the
dictionary meaningfully exceeds the cap.

```bash
python DQC/eval/schema_linking.py                  # report
python DQC/eval/schema_linking.py --fail-under 1.0 # CI gate
python DQC/eval/schema_linking.py --no-embedder    # isolate the semantic channel
```

**Caveat on that number.** `dqc_react._field_embedder()` returns `None` in this
environment — no embedding index is built — so both the measurement *and*
generation are running the lexical channel alone. The semantic channel may
recover some of these fields; that comparison needs an index and has not been
run. Treat 0.938 as the lexical-only floor.

---

## Gap 5 — other techniques worth adding

Ordered by value per unit of effort.

### 5.1 Ambiguity / refusal quality — **highest value, lowest effort**

`check_sufficiency` decides whether a rule is answerable at all, and the trace
records `¿Información suficiente?` with a yes/no. Only 2 of 16 golden traces
are adversarial, and refusal is not scored as its own task.

A system that confidently generates SQL for an ambiguous rule is *worse* than
one that asks — it produces a plausible control nobody can audit. Build a set
of deliberately under-specified rules (missing field, ambiguous threshold,
undefined business term, contradictory conditions) and score refusal precision
and recall separately from generation quality. Over-refusal is its own failure:
a system that asks for clarification on everything is useless too.

### 5.2 Cost and latency alongside accuracy

Nothing in `eval_harness.py` records tokens, cost or elapsed time. A prompt
change that buys 2 points of recall for 3× the tokens should be visible at
review time, not discovered on the invoice. Log input/output tokens, wall time
and attempts per rule; report cost-per-rule next to every accuracy number.

### 5.3 BCBS 239 classification accuracy

Issue #2 assigns a BCBS 239 dimension to every generated DQC, and nothing
scores it. It is a plain multi-class classification problem: label the golden
set and report a confusion matrix. Regulatory mislabelling is a compliance
risk, not a cosmetic one, and per-class recall will show which dimensions the
model conflates.

### 5.4 Perturbation / robustness

Semantically neutral rewrites of the same rule must produce equivalent SQL:
Spanish ↔ English, formal ↔ colloquial, field named in prose vs by exact column
name, reordered clauses. Report `consistency_rate` — the fraction of
perturbation groups whose members agree. This catches brittleness that the
golden set, with one phrasing per rule, cannot.

### 5.5 Dictionary-perturbation / grounding

Rename a column in the dictionary and re-run. The generated SQL must follow the
rename. If it still emits the old name, the model is recalling training data
rather than reading the provided dictionary — a grounding failure that
correctness-on-the-golden-set will never reveal.

### 5.6 Contamination check

Before trusting any headline number, confirm the model has not memorised the
fixtures. Rename tables and columns to synthetic identifiers and re-run: a
large drop means the score was partly recall, not reasoning.

### 5.8 EBA guidelines as a rule-proposal surface

`regulation_chunker.py`, `regulation_vector_store.py` and
`build_regulation_embeddings.py` ingest 221 paragraphs of EBA GL/2017/16, and
`DQC/coverage/applicability.yaml` maps sections to fields. **Nothing in the
serving path imports the store** — only the builder script and a slim-imports
test. It is the highest-value unconnected asset in the repo.

Wiring it as a *proposal* surface:

- **Drive it from the coverage matrix.** Propose only for UNCOVERED
  field × article cells. That turns the matrix from a report into a work queue
  with a natural stopping condition.
- **Propose, never auto-apply.** `applicability.yaml`'s own header requires
  every entry to be human-reviewed. A regulator-facing control that appeared
  without approval is worse than a missing one.
- **Attribute, do not assert.** Use `units_from_reg_chunks` + ablation so each
  proposal carries the paragraph whose removal would have changed it.
  `golden_eval.py` already detects invented references; this prevents them.

Caution: the guidelines state obligations on the *institution*, not row-level
predicates. Many paragraphs have no testable DQC. Make "not testable" a
first-class outcome, or the model will invent checks to satisfy coverage —
the reward-hacking the mixed-DB confusion matrix exists to catch, arriving
through a new door.

### 5.7 Human spot-audit

Sample ~20 generated checks per release for blind expert review, scored on the
same rubric as the judge. This is the anchor that keeps every automated number
honest, and it is what makes the judge-calibration numbers credible to an
auditor.

---

## Suggested order

1. Judge calibration + the fail-open fix (Gap 1) — the judge currently gates
   production output with zero measurement.
2. Retry metrics (Gap 3) — pure instrumentation over traces you already emit.
3. Temperature 0 and variance measurement (Gap 4) — small change, makes every
   other number trustworthy.
4. **Schema-linking recall (Gap 6) — measured at 0.938 and capping everything
   downstream.** Fix the cap before tuning any prompt.
5. Ambiguity/refusal set (5.1) — the largest untested behaviour.
5. Cost/latency (5.2), then BCBS classification (5.3).
6. Position/verbosity bias (Gap 2) — **before** building any pairwise
   comparison, not after.
7. Perturbation and grounding (5.4, 5.5), contamination (5.6), human audit (5.7).

---

## Related

- [`SAS_CONNECTIVITY.md`](SAS_CONNECTIVITY.md) — whether generated DQCs can be
  submitted to a real SAS server, and the 31 classified failure modes.

## Open questions for the council

- Is pointwise judging enough, or does the correction loop need pairwise
  comparison of candidate SQLs? If pairwise, position bias must be handled
  from the start.
- Should the judge fail **closed** (reject on error) in a regulated context,
  accepting a lower yield for a stronger audit position?
- Is `MAX_ATTEMPTS = 3` right? The retry metrics will answer this empirically
  rather than by assertion.
- Who writes the golden SQL? If the prompt author writes it, the eval encodes
  the model's current idiom as truth and will flatter every future change.
