# Plan

## Overview
This is a market & pricing assessment for the RegLLM/DQC PoC (regulation-grounded generator of certified data-quality checks for Spanish credit/risk pipelines), covering the Spain-only niche: ~10–15 Significant Institutions, ~73 LSIs via Banco de España, and a 3–5 firm consultancy channel. Headline recommendation: price the **consultancy white-label accelerator as the primary motion** — partner licence €40K–€60K/yr + €30K–€50K/yr per regulation-corpus module + €25K–€35K per generated audit-pack engagement — and a **direct-SI tier secondarily at €90K–€120K/yr per corpus module** (pilot €45K–€60K, 4–6 weeks), anchored between the consultancy incumbents' €200K–€500K recurring hand-written engagements and the $170K–$500K/yr Collibra/observability stack, with defensibility resting on the repo's real, execution-proven assets: the field × article coverage matrix (`DQC/eval/coverage_matrix.py`), the no-LLM-judge mutation harness (`DQC/eval/eval_harness.py`), the Spanish GL/2017/16 corpus, SAS field-diff tooling, and the on-prem GGUF/Ollama path (`config.yaml`, `src/knowledge/llm_client.py`).

## Scope
- In:
  - Competitor price map covering Collibra, Soda.ai (Core/Cloud), Monte Carlo, Anomalo, Bigeye, Validio, Ataccama ONE, Informatica, Stratio/Datio, OSS (Great Expectations, dbt tests + dbt-expectations, Soda Core, Elementary, Deequ), consultancy incumbents (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4), and reporting vendors (Wolters Kluwer, Regnology) — figures only from the repo memos, with unverified items flagged.
  - Concrete price points and packaging: per-corpus-module, per-SI annual, per-engagement audit pack, partner price band — with segment arithmetic.
  - Differentiation ("where we win / where they still beat us") grounded strictly in confirmed repo capabilities (generator + review UI, RAG/GraphRAG, harness, coverage matrix, SAS field-diff explainer, local-LLM, cross-table/date defects D48–D57).
  - Value/ROI narrative, GTM motion, pilot validation, rollback ladder, segment edge cases.
- Out:
  - Global market sizing (Spain only, per brief).
  - Implementation/engineering work beyond what supports pricing claims (no scheduler, incident-triage agent, or dialect compiler is claimed — none exists).
  - Inventing competitor prices or capabilities; anything marked (ASSUMPTION — verify) is routed to the analyst in Phase 1.
  - Building the Anejo IX / Circular 4/2017 corpus or audit-pack one-command generator (both are roadmap items, priced as future modules, not sold as present capability).

## Phases

### Phase 1: Competitor price landscape map (verification-first)
**Goal**: Produce a defensible price table with every figure either sourced from the repo memos or explicitly flagged for verification.

#### Task 1.1: Consolidated price map
- Location: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` (§2, §4), `docs/DATA_QUALITY_SPAIN_NICHE.md` (§3–4), output to `docs/PRICING_ASSESSMENT_ES.md` (new).
- Description: Build the Spain-relevant competitor table: Collibra base ~$170K, DQ module ~$156K budgeted separately, governance suite all-in $170K–$295K pre-services; full enterprise stack $200K–$500K/yr; managed observability (Monte Carlo, Anomalo, Bigeye, Validio) $50K–$200K+/yr; Ataccama ONE from ~$90K; Soda Core free OSS / Soda Cloud paid (price UNVERIFIED); OSS $0 licence + ~0.5–1 FTE; consultancy hand-written DQ-rules engagement €200K–€500K recurring (3–4 people, Management Solutions/NTT Data/Minsait/Accenture/Big 4). Note Stratio/Datio as local platform player (pricing UNVERIFIED) and Wolters Kluwer/Regnology as bundled EBA-rule executors. Record supporting economics: 6+ month governance implementations, ROI ~month 25, Gartner $12.9M/yr poor-DQ cost.
- Estimated Tokens: 8000
- Dependencies: none
- Steps:
  - Extract every figure with its memo section as provenance.
  - Split columns into "verified from repo memos" vs "ASSUMPTION — verify".
  - Add per-segment relevance: SI-direct, LSI-via-consultancy, incumbent-in-place.
- Acceptance Criteria:
  - Table covers all named competitors with at least a price tier or an explicit "unverified" flag; zero invented numbers.

#### Task 1.2: Verify the four load-bearing unknowns
- Location: analyst work; results appended to `docs/PRICING_ASSESSMENT_ES.md`.
- Description: (1) Soda Cloud list price and packaging; (2) Collibra street discounts in Spain (list vs real, commonly discounted); (3) Ataccama ES deal sizes; (4) consultancy day-rate check that €200K–€500K/3–4-person/recurring holds for 2026 (ASSUMPTION — verify). Also fix an FX policy: USD anchors converted at an assumed ~0.9 EUR/USD (ASSUMPTION — verify rate and whether competitors quote EUR list in ES).
- Estimated Tokens: 5000
- Dependencies: Task 1.1
- Steps:
  - Obtain one written quote each via resellers/partners where possible.
  - Re-run the pricing arithmetic in Phase 3 against verified numbers; if ES street pricing is ≥30% below list, trigger the Rollback Plan step 1 immediately.
- Acceptance Criteria:
  - Each of the four unknowns is either resolved with a dated source or carries a stated fallback assumption in the price list.

### Phase 2: Packaging model (units and tiers)
**Goal**: Define what is sold — the licensed unit is the regulation-corpus module, not seats, checks, or fields.

#### Task 2.1: Define the three sellable units
- Location: grounded in `DQC/coverage/applicability.yaml` (per-corpus applicability maps), `DQC/eval/eval_harness.py` + `coverage_matrix.py --fail-under 1.0` (certification artifacts), `docs/MVP_ROADMAP.md` (corpus roadmap: Anejo IX → COREP/FINREP import → CIRBE/AnaCredit).
- Description: Packaging:
  1. **Corpus module** (e.g., "EBA GL/2017/16 ES"; future "Anejo IX / Circular 4/2017"): applicability map + certified check battery + amendment-regeneration rights. Flat price per module — never per-check/per-field, because the value proposition is 100% coverage and per-unit pricing would contradict it.
  2. **Audit pack** (per-engagement consumable for the consultancy channel): the generated, harness-certified, bilingual ES/EN check suite + evidence bundle for one client engagement.
  3. **Deployment**: on-prem local-LLM (Ollama/GGUF backend in `config.yaml`, `src/knowledge/llm_client.py`) as the default contract posture; Bedrock/Azure backends as opt-in only.
- Estimated Tokens: 6000
- Dependencies: Task 1.1
- Steps:
  - Write the packaging one-pager with explicit exclusions (no scheduler, no incident triage, one corpus shipping today — GL/2017/16 ES; 221 ingested paragraphs; Anejo IX is a roadmap module).
  - Map each unit to an existing repo artifact so sales claims are demonstrable in a demo (`demo/` runs LLM-free).
- Acceptance Criteria:
  - Every priced unit traces to a demonstrable repo artifact; the one-pager lists current gaps (58/59 applicability entries pending human sign-off; 8/51 matrix cells partial per the SOTA memo) as known remediation items.

### Phase 3: Segment pricing math
**Goal**: State numbers with the arithmetic showing how each segment is priced and why it is defensible against Collibra and Soda.

#### Task 3.1: Direct-SI tier
- Location: arithmetic vs `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` §4 anchors.
- Description and math:
  - **Pilot**: €45K–€60K fixed fee, 4–6 weeks, one corpus, one schema — ≈25–30% of the low end of a hand-written engagement (€200K) and ≈1/3 of Collibra base alone ($170K ≈ €155K at assumed FX). Sized to sit under a plausible ES discretionary spend threshold (ASSUMPTION — verify ~€50K–€60K no-RFP threshold).
  - **SI annual subscription**: €90K–€120K/yr per corpus module, on-prem, includes amendment-regeneration (corpus re-hash flips affected sections to `pending`; the delta re-runs the certification) and bilingual pack. Two-corpus bundle (GL/2017/16 + Anejo IX) €140K–€180K/yr.
  - Defensibility vs Collibra: base ($170K) + DQ module ($156K) ≈ $326K ≈ €295K before services (ASSUMPTION FX); our bundle at €140K–€180K is ~40–55% of that, delivers article-level execution-proven coverage that the DQ module cannot, with weeks-not-months time-to-value (ROI ~month 3–6 vs their month 25).
  - Defensibility vs Soda: Soda Core is free, so we never win on the SQL itself — we win on the certified corpus and audit pack; the SI price is justified as replacing the €200K–€500K recurring hand-authoring engagement, not as a better rule runner.
- Estimated Tokens: 7000
- Dependencies: Tasks 1.1, 1.2, 2.1
- Steps:
  - Build the price ladder table (pilot → single module → bundle → multi-corpus enterprise).
  - State per-line the counterfactual it replaces (consultancy engagement / Collibra module / OSS+FTE).
- Acceptance Criteria:
  - Every SI price line has a counterfactual cost comparison and a "why not cheaper" rationale; no line depends on an unverified number without a flag.

#### Task 3.2: Consultancy white-label partner program (primary channel)
- Location: economics vs `docs/DATA_QUALITY_SPAIN_NICHE.md` §4.
- Description and math:
  - **Partner platform licence**: €40K–€60K/yr per consultancy (internal use, named practitioners, includes licensed modules).
  - **Per-corpus-module delivery licence**: €30K–€50K/yr per module held by the partner.
  - **Per-engagement audit-pack fee**: €25K–€35K per client engagement.
  - Partner economics: their hand-written equivalent costs €200K–€500K recurring (3–4 people). First-year cost with us ≈ €50K module midpoint + €30K engagement ≈ €80K + ~1 person-month of their review; they resell the engagement at €150K–€250K (winning deals under their own legacy floor) or keep €200K+ for margin — €70K–€170K gross margin per engagement vs ~zero incremental margin on hand-written hours.
  - New segment unlocked: LSI audit packs at €80K–€120K resale — previously below their cost floor; the ~73 LSIs become reachable only through this structure.
  - Amendment flywheel: each circular amendment (e.g., Circular 1/2025 touching Anejo IX) flips affected sections to `pending` — the delta regeneration becomes a re-billed engagement instead of a cost sink.
  - Discipline rules: engagement fee capped at ~20% of the partner's resale price; white-label means the partner's brand on the pack, our presence only in machine-verifiable provenance (git SHA, harness JSON, matrix output) if the client demands source.
- Estimated Tokens: 7000
- Dependencies: Tasks 2.1, 3.1
- Steps:
  - Draft partner terms outline (licence scope, per-engagement fee, exclusivity policy: at most corpus-level exclusivity, never global — with only 3–5 viable partners, global exclusivity to one destroys the channel).
  - Build the partner margin model spreadsheet-equivalent in the assessment doc.
- Acceptance Criteria:
  - A partner reading the model sees margin expansion and a new LSI segment, with no line requiring them to cut headcount; terms document states the exclusivity position.

### Phase 4: Differentiation matrix (win/lose per competitor)
**Goal**: Specific, capability-grounded positioning; no over-claiming.

#### Task 4.1: Write the win/lose matrix
- Location: evidence in `DQC/eval/` (harness, `defect_catalog.py` 67-defect catalog, `coverage_matrix.py`), `src/knowledge/` (GraphRAG, regulation vector store, multi-backend LLM), `api/routers/dqc.py` (generate/review flow), `src/__init__.py` + `src/knowledge/graph_rag.py` (SAS field-diff explainer: autograd + Shapley + GraphRAG), `docs/DATA_QUALITY_SPAIN_NICHE.md` §6.
- Description: For each competitor, "where we win" / "where they still beat us":
  - **Collibra**: Win — article-level, execution-proven coverage vs asserted CDE × dimension matrices; no-LLM-judge certification; ES corpus/citations; on-prem local-LLM; ~½ price; weeks vs 6+ month implementation. Lose — stewardship workflow, CDE registries, enterprise lineage breadth, integrations, brand safety and incumbency at the largest groups; they remain the governance system of record.
  - **Soda.ai**: Win — regulation-derived checks vs hand-authored; certified per-article coverage; bilingual ES/EN audit pack; SAS artifact story. Lose — $0 entry (Soda Core), dbt-native workflow, community, Cloud monitoring/alerting maturity, and their active BCBS 239/RDARR marketing.
  - **Monte Carlo** ($50K–$200K+): Win — known-invariant regulatory coverage vs learned normality; auditability per article; on-prem no-egress; lower price. Lose — anomaly detection for unknown-unknowns; shipped incident-triage agents (we have none).
  - **Anomalo**: same win/lose shape; they add ML checks on data content and LLM-data monitoring.
  - **Bigeye, Validio**: same tier; they win observability UX/breadth; we win certification, grounding, price floor, on-prem.
  - **Ataccama ONE** (~$90K+): Win — certified regulation coverage + ES corpus + local-LLM at comparable entry price. Lose — platform maturity (profiling, remediation, MDM adjacency) and reference base.
  - **Informatica**: Win — price, regulation grounding, on-prem LLM, SAS focus. Lose — platform breadth and installed base in the largest ES groups.
  - **Stratio/Datio** (local): Win — regulatory certification depth, SAS artifact, local-LLM egress story. Lose — local enterprise relationships (BBVA/Datio alliance), data-fabric breadth, local support presence.
  - **OSS (GE, dbt tests + dbt-expectations, Soda Core, Elementary, Deequ)**: Win — zero-authoring certified coverage; corpus maintenance on every amendment; the audit pack as an artifact. Lose — $0 licence and engineer preference; credible fallback if a bank spends the 0.5–1 FTE (≈€60K–€100K salary, ASSUMPTION — verify ES comp) — our defence is certification + maintenance, not the SQL.
  - **Consultancy incumbents**: as competitors they hand-write at €200K–€500K recurring; we win on cost curve, consistency, amendment speed — but we never sell against them to LSIs; we white-label through them. Lose — relationships, advisory breadth, staffing flexibility.
  - **Wolters Kluwer / Regnology**: Win — we check the data layer before submission (BdE rejects submissions failing EBA DPM rules; catching them pre-submission is the pitch). Lose — they own the reporting workflow and bundle EBA rule execution.
  - Explicit non-claims (stated in the doc): no scheduler, no incident-triage agent, one shipping corpus, SQLite eval DB (no dialect compilers), no SaaS multi-tenancy.
- Estimated Tokens: 9000
- Dependencies: Tasks 1.1, 2.1
- Steps:
  - One row per competitor with evidence pointer (repo path or memo section) per claim.
  - Add the "moat stack" summary: (i) generation + machine-verifiable field × article coverage (proof-by-execution), (ii) deterministic mutation harness, no LLM judge, recall=1.0 gate, (iii) ES corpus + bilingual ES/EN output, (iv) SAS field-diff explainer (Shapley + GraphRAG) — the artifact Spanish risk teams live in, (v) on-prem GGUF/Ollama so schema never leaves the bank, (vi) regenerable coverage per circular amendment.
- Acceptance Criteria:
  - Every "we win" claim cites a repo artifact that can be demoed; every "they beat us" admission is present for all 12+ entries; zero claims of unbuilt features.

### Phase 5: Go-to-market motion
**Goal**: Sequence the channel so the first euro comes from the motion most likely to pay.

#### Task 5.1: Channel sequencing and buyer mapping
- Location: `docs/DATA_QUALITY_SPAIN_NICHE.md` §2, §6 (personas: head of Calidad del Dato/CDO office, head of validación interna, intervención general for Anejo IX; consultancies as LSI buyers).
- Description: (1) Sign 1 design-partner SI validation department + 1–2 consultancies in parallel. (2) Lead commercial conversations with mid-tier SIs (Unicaja, Ibercaja, Cajamar, Abanca, Bankinter) — Santander/BBVA procurement will not buy at PoC maturity; treat G-SIBs as year-2. (3) Consultancies open the LSI segment (€80K–€120K packs). (4) Reference-driven sales only — one SI validation department as design partner is worth more than marketing; pitch in local terms: "cada párrafo aplicable de la GL/2017/16 tiene un control que demostrablemente dispara".
- Estimated Tokens: 5000
- Dependencies: Phase 2, 3
- Steps:
  - Build a named account map (10–15 SIs, 3–5 consultancies) with persona, entry corpus, and target price per account.
  - Draft the white-label one-pager and the SI pilot one-pager (ES/EN).
- Acceptance Criteria:
  - Every target account has a persona, motion (direct vs via partner), and price; G-SIBs explicitly deferred with rationale.

### Phase 6: Launch steps
**Goal**: Convert the assessment into a priced offer with a validated pilot.

#### Task 6.1: Publish price list v1 and run the pilots
- Location: `docs/PRICING_ASSESSMENT_ES.md`; pilot acceptance gates in `DQC/eval/README.md` commands.
- Description: Publish internal price list v1 (pending Phase 1 verifications). Run the pilot per Testing Strategy. Before first external sale, close the sales-blocking repo gaps: drive the 58 `review: pending` applicability entries to approved and tighten partial cells (per `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` §6.1–6.2) — selling a certification that the repo itself has not yet reached at 1.0 is a diligence failure waiting to happen.
- Estimated Tokens: 6000
- Dependencies: Phases 1–5
- Steps:
  - Gate: applicability pending = 0 and matrix 0 todo for the pilot scope before signing pilot contracts.
  - Assemble the audit-pack evidence bundle manually from existing outputs (applicability.yaml + matrix JSON + harness JSON + git SHA) — note the one-command audit-pack generator is a roadmap item, not present in this branch.
  - Log every commercial conversation (objections, price anchors) in the win/loss log.
- Acceptance Criteria:
  - Price list v1 published with verification flags cleared or annotated; pilot contracts signed with acceptance criteria embedded; win/loss log live.

## Testing Strategy
- **Discovery pricing tests (weeks 1–4)**: 5–8 structured calls (3+ SI Calidad del Dato / validación interna heads; 3–5 consultancy partners). Test anchors: €45K–€60K pilot, €90K–€120K SI annual, €80K first-year partner cost. Record acceptability (too cheap / acceptable / too expensive) per respondent; an anchor rated "too cheap" by ≥half the SI respondents triggers a ladder re-test at +25%.
- **Design-partner pilot (weeks 4–10)**: 1 SI + 1 consultancy, 4–6 weeks, at pilot price. Acceptance criteria: (a) the audit pack is used in a real supervisory or internal-validation conversation; (b) `python DQC/eval/eval_harness.py --sql <pilot_checks>.sql --fail-under 1.0` passes on the pilot check set; (c) `python DQC/eval/coverage_matrix.py --fail-under 1.0` passes for pilot scope (0 todo); (d) amendment-regeneration demo: a synthetic Circular-1/2025-style corpus delta flips affected `applicability.yaml` sections to `pending` and re-certifies; (e) bilingual ES/EN pack accepted by the ES team and readable by an EN-only reviewer; (f) on-prem run with zero data egress (GGUF/Ollama or stub backend; `demo/` proves the LLM-free path).
- **Competitor price verification**: one written quote each for Collibra DQ module, Soda Cloud, Ataccama via resellers; document street discounts; recompute the ladder (Task 1.2).
- **Partner-economics test**: a signed white-label LOI at target fees (licence + ≥2 engagements in 2 quarters) validates the primary channel; 2 pilots stalling above €60K triggers Rollback step 1.
- **Win/loss instrumentation**: every opportunity logged with price objection reason; monthly review against the ladder.

## Risks
- **Self-critique: the price anchors are secondary-source, mostly US-dollar figures.** Collibra module prices, the €200K–€500K consultancy day-rate math, and the observability tiers come from the repo memos, not Spanish street quotes; enterprise discounting commonly runs 30–50% off list, so the entire €90K–€120K SI tier could be priced above local willingness to pay and the ladder would need re-basing after Task 1.2. The plan publishes no external price list until that task closes, but if verification fails late, pilot contracts already negotiated at anchor prices create renegotiation friction.
- **Self-critique: the white-label thesis assumes consultancies see margin expansion rather than a threat.** Big 4 or Management Solutions could replicate a "good-enough" LLM rule generator internally for less than one year of partner licence fees; the moat (certification harness + ES corpus) is one regulation deep until Anejo IX ships, and a partner may respond by demanding exclusivity or acquisition instead of signing. The corpus-level exclusivity stance and the amendment-flywheel recurring revenue are the mitigations, but both are untested assumptions about partner behaviour.
- **Self-critique: sales claims currently outrun repo state.** 58/59 applicability entries are `review: pending`, 8/51 matrix cells are only `partial`, the recall gate is not pinned at 1.0 in CI for the shipped check set, and `apdq/` (binding manifest, one-command audit-pack generator — claimed implemented in `docs/MVP_ROADMAP.md`) is absent from this branch. Any bank diligence pass finds this; the plan gates pilot contracts on closing the coverage gaps, but if the gap-closing slips, the pilot either ships with a weaker "certified" story or slips too.
- **Concentration risk**: 10–15 direct accounts; losing one champion (a single Calidad del Dato head changing roles) can stall a full year's direct revenue. Mitigation: run the consultancy channel in parallel from day one.
- **Mid-tier price drift**: early revenue will come from thinner-budget SIs (Unicaja, Ibercaja, Cajamar), pulling blended price below €90K and weakening the Collibra-anchored story. Mitigation: hold the module price, discount deployment/onboarding services instead.
- **"100% coverage" is relative to our own 67-defect catalog**; auditors will challenge circularity. Mitigation: state the limitation in the pack and roadmap the LLM-generated novel-defect ratchet (`docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` §6.4) before the first external audit conversation.
- **OSS commoditisation**: dbt + Elementary + an internal LLM script covers 60–70% of the demo for a skeptical buyer. Mitigation: always demo the certification artifact and amendment regeneration, never the raw SQL.

## Rollback Plan
1. **Price ladder step-down**: SI €90K–€120K → €75K "single-corpus essentials" (no bundle, quarterly-not-event amendment cadence) → €60K (pilot price retained as annual). Partner per-engagement fee €25K–€35K → €20K flat; keep the module licence intact to protect the anchor.
2. **Channel pivot**: if white-label stalls on terms/exclusivity, pivot to direct-SI with 2 design partners at €60K pilots; if direct stalls, reposition as embedded tooling inside consultancy engagements at a sub-€25K line-item licence to keep logos and references alive.
3. **Reposition vs OSS**: if generation commoditises, sell corpus maintenance + the certification artifact only ("corpus-as-a-service", €30K–€50K/yr per module) — the amendment-delta regeneration is the hardest part to replicate for free.
4. **Corpus pivot**: if GL/2017/16-only doesn't land and Anejo IX slips, generalise the already-built cross-table reconciliation families (D48–D57 in `DQC/eval/defect_catalog.py`) into a CIRBE/AnaCredit ↔ datamart reconciliation module as the second sellable corpus.
5. **Floor rule**: never give the licence away free — cost-recovery reference engagements (€25K) maximum; a free deployment destroys the anchor for all 10–15 accounts.

## Edge Cases
- **LSIs (~73, via consultancy only)**: never sold direct; served exclusively as €80K–€120K partner packs; monitor that white-label provenance (git SHA, harness JSON) does not leak our brand where the partner wants it absent — and vice versa, that partners cannot strip provenance and resell as fully theirs.
- **Banks with hard data-egress rules**: on-prem GGUF/Ollama is the contract default (`config.yaml` backends); Bedrock/Azure backends are opt-in only; the `demo/` kit runs LLM-free so even the sales demo can promise zero egress. An EU-hosted managed tier (eu-west-1 Bedrock) can be offered as a priced opt-in if a bank demands it.
- **Banks already on Collibra/Informatica**: do not compete for the governance layer; position as the "rules + certification" complement priced at €60K–€90K alongside the incumbent — displacing an installed governance suite is a 2-year sale we cannot afford in a 15-account market.
- **Tourism/savings co-ops (Cajamar, Unicaja)**: their highest-value corpus is arguably Anejo IX (adjudicados, stages, coverage levels), which is not built — sequencing risk; sell the IRB PD/LGD angle only where their portfolio justifies it, or route through the partner channel where engagement scope can absorb the wait.
- **G-SIB (Santander)**: deferred to year 2; procurement will not engage at PoC maturity; a premature attempt risks a public "not ready" verdict in a reference-driven market.
- **Currency**: publish the SI and partner list in EUR; USD competitor anchors carry a stated FX assumption (ASSUMPTION — verify) so the "½ of Collibra" claim survives a EUR-list quote from Collibra Spain.
- **Supervisory-conversation mismatch**: the pack certifies GL/2017/16; an IMI or BdE inspection may scope RDARR or Anejo IX — sales must scope claims per corpus and never imply whole-BCBS 239 certification (the RDARR layer maps to governance evidence, not row-level oracles, per `docs/DATA_QUALITY_SPAIN_NICHE.md` §5).

## Open Questions
- What is Soda Cloud's actual list price/packaging, and what street discounts do Collibra and Ataccama give in Spain? (Task 1.2 — load-bearing for the whole ladder.)
- Will Management Solutions, NTT Data, or Minsait sign a white-label licence, or do they respond with exclusivity/acquisition demands — or by building their own?
- Do Spanish SI DQ offices hold discretionary authority around €45K–€60K without a platform RFP (assumed threshold ~€50K–€60K — verify)?
- `docs/MVP_ROADMAP.md` claims MVP items 1–7 (binding manifest, manifest-driven twin generator, one-command audit-pack generator) are implemented in `apdq/`, which is absent from this branch — which branch is the product truth, and does the audit-pack artifact exist anywhere today?
- Build time and cost for the Anejo IX / Circular 4/2017 corpus (the highest-value Spanish extension per `docs/DATA_QUALITY_SPAIN_NICHE.md` §5), and must the first pilot wait for it for the Cajamar/Unicaja-type accounts?
- Does the SAS story hold at pilot scale — the repo has the SAS field-diff explainer (Shapley + GraphRAG) and the AST differ demo, but full SAS→IR transcription is roadmap item 10; can we credibly demo on a real bank SAS estate in 4–6 weeks?
- Is the €12.9M/yr Gartner poor-DQ figure usable in ES buyer conversations, or does it read as US-market inflation to Spanish risk officers?
- Would importing EBA COREP/FINREP DPM validation rules (roadmap) be read by Wolters Kluwer/Regnology incumbents as channel conflict, and does that help or hurt the consultancy channel?