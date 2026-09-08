# Plan

## Overview

Produce a defensible Spain-only market & pricing assessment for the RegLLM / DQC PoC, mapping the full competitor landscape against a primary consultancy white-label accelerator channel plus a direct significant-institution (SI) tier, and recommending a concrete price point, packaging and differentiation narrative grounded in the repo's actual capabilities (harness, coverage matrix, RAG, SAS AST differ, local-LLM path) rather than its roadmap. Headline recommendation: license the accelerator white-label to 2–3 consultancies at €60K–€90K/yr plus €8K–€15K per certified audit pack per corpus per supervisory cycle, and sell direct to Spanish SIs at €45K–€60K per regulation-corpus module per year (€85K–€120K bundled), a fraction of Collibra-with-DQ (~$300K+) and of one incumbent engagement (€200K–€500K).

## Scope

- In: competitor price mapping (global + Spain-local players); a two-channel packaging model (consultancy white-label primary, direct SI secondary); segment pricing math with defensible arithmetic; per-competitor differentiation ("where we win" / "where they beat us"); a value/ROI narrative; go-to-market motion; launch steps; a pilot-driven pricing-validation strategy; market risks (incl. self-critique); rollback; segment edge cases; open questions.
- Out: any software build, refactor or engineering plan beyond a one-line mention that capabilities exist; any global (non-Spain) market sizing; development of the Anejo IX / COREP-FINREP modules (assumed to exist only as roadmap, and flagged as such); incident-triage agent or scheduler (both roadmap, not claimed).

## Phases

### Phase 1: Competitor price mapping (validate the anchors)
**Goal**: Convert the repo's research figures into a single normalised price ladder with Spanish context, and set the value anchors every later price point is tested against.

#### Task 1.1: Normalise the global price ladder
- Location: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` (source figures), `docs/DATA_QUALITY_SPAIN_NICHE.md`, output to `docs/PRICING_ASSESSMENT.md` (new).
- Description: Build one comparison table of list price, module-of-record, and typical all-in annual cost per vendor; explicitly separate "list" from "all-in w/ services" for Collibra (base ~$170K, DQ module ~$156K budgeted separately, governance suites $170K–$295K before services, full stack $200K–$500K), and note Soda Core is free OSS while Soda Cloud is the paid tier.
- Estimated Tokens: 900
- Dependencies: none.
- Steps:
  - Transcribe each figure verbatim with its source memo and a `verify:` flag (mark Collibra/Soda/Ataccama as analyst-to-verify since they are secondary-source estimates, not live quotes).
  - Collapse observability vendors (Monte Carlo, Anomalo, Bigeye, Validio) into one "$50K–$200K+/yr managed observability" row where their pricing behaviour is identical for positioning purposes.
- Acceptance Criteria:
  - A single price table where every row has list, all-in, and an explicit provenance note plus a to-verify marker.
  - A clearly labelled "value anchors" subsection: (a) ~$200K–$500K/yr for a regulated enterprise stack, (b) €200K–€500K/yr recurring per 3–4-person consultancy engagement.

#### Task 1.2: Add the Spain-local price layer
- Location: `docs/DATA_QUALITY_SPAIN_NICHE.md`, `docs/PRICING_ASSESSMENT.md`.
- Description: Add Stratio / Datio (Madrid data fabric), the consultancy incumbents (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4), and note that LSIs under Banco de España mostly cannot buy at global platform prices.
- Estimated Tokens: 700
- Dependencies: 1.1
- Steps:
  - List each Spain player with its segment, and mark that the €200K–€500K/3–4-person figure is an engagement estimate, not a verified rate card (flag as a to-verify; EU/Spanish day rates diverge from US).
  - Note the LSI outcome-buyer behaviour (they buy outcomes, not platforms) as the reason a per-pack price floor exists.
- Acceptance Criteria:
  - A Spain-specific competitor row set and an explicit note that the consultancy engagement figure is an assumption to be validated in Phase 6 discovery.

#### Task 1.3: Set the defensibility envelope (floor vs ceiling)
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Define the price corridor: floor = OSS (free + ~0.5–1 FTE engineering); ceiling = Collibra-with-DQ (~$300K+) and one incumbent engagement (€200K–€500K). Position all recommended prices strictly between, and state the only justification for being above zero (regulation-grounded, proof-by-execution coverage).
- Estimated Tokens: 500
- Dependencies: 1.1, 1.2
- Steps:
  - Write the floor/ceiling statement and a one-line "why not free" clause (certification + Spanish + SAS + on-prem), used verbatim in Phase 5 collateral.
- Acceptance Criteria:
  - A stated corridor and the exact justification for a non-zero price.

### Phase 2: Packaging & price-point model (the core deliverable)
**Goal**: Recommend concrete price points and packaging for both channels, with arithmetic.

#### Task 2.1: Define the module/tier structure
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Price the unit of sale, not the platform. Modules = corpus modules: A = EBA GL/2017/16 (built today), B = Anejo IX / Circular 4/2017 (roadmap, flag), C = EBA COREP/FINREP validation-rule import (roadmap, flag). Channel tiers = direct SI annual license, consultancy white-label license, per-audit-pack fee, partner wholesale price band.
- Estimated Tokens: 600
- Dependencies: 1.3
- Steps:
  - Define four packages: (1) per-corpus module, (2) per-SI annual license (1 vs 2–3 modules bundled), (3) per-engagement/per-audit-pack, (4) partner white-label band.
  - Explicitly mark module B and C as not-yet-built and therefore an aspirational portfolio, not today's sellable module.
- Acceptance Criteria:
  - Four named packages, each with a one-line buyer and the capability it maps to (or its roadmap flag).

#### Task 2.2: Compute segment pricing math
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Show the arithmetic per segment and why each point is defensible.
- Estimated Tokens: 1000
- Dependencies: 2.1
- Steps:
  - Direct SI: module A = €45K–€60K/yr; bundle A+B = €85K–€120K/yr; one-time onboarding/setup (dictionary ingest + applicability sign-off session + SAS lineage import) = €15K–€20K once. Arithmetic vs Collibra: Collibra base ~$170K + DQ ~$156K ≈ $326K/yr before services; our €60K is ~25–35% of Collibra base, and our all-in bundle is less than the Collibra DQ module alone; vs the €200K–€500K stack we are ~15–25%.
  - Consultancy white-label: partner license = €60K–€90K/yr per consultancy; per-certified-audit-pack wholesale = €8K–€15K per corpus per SI per cycle. Arithmetic vs engagement: an average engagement midpoint ≈ €350K (€200K–€500K range); a 50% delivery-effort reduction (pilot-measured, not asserted) leaves the consultancy fatter margin; a €60K license is ~17% of a single €350K engagement and ~8% of a two-engagement book, well under the effort it removes. Partner band = 50–70% off direct list on packs.
  - LSI channel: no platform sale; per-pack wholesale €8K–€15K through the consultancy, which marks up to the LSI (retail pack ≈ €15K–€25K).
  - Explicitly state that the 50% effort-reduction figure is a *hypothesis to be measured in the pilot* (Phase 6), because the price is anchored on it.
- Acceptance Criteria:
  - Every recommended number is accompanied by a calculation and a stated assumption where the input is an estimate.

#### Task 2.3: Write the defensibility statement
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: One paragraph proving the price is defensible against Collibra and Soda specifically: we undercut Collibra's governance-stack price and its 6+month/25-month-ROI burden with a code-first, certified artifact; we sit above the Soda/OSS free floor only because we produce regulation-attributed, proof-by-execution coverage Soda is not designed to deliver.
- Estimated Tokens: 500
- Dependencies: 2.2
- Steps:
  - Draft the statement in three sentences: what the buyer gets, what it costs vs Collibra (cheap + fast + certified), and why it isn't free vs OSS/Soda (proof, not assertions).
- Acceptance Criteria:
  - A copy-paste defensibility paragraph usable in decks and valuation discussions.

### Phase 3: Differentiation map (where we win / where they beat us)
**Goal**: Produce a specific, actionable per-competitor win/lose table grounded only in shipped capabilities.

#### Task 3.1: Build the per-competitor win/lose table
- Location: `docs/PRICING_ASSESSMENT.md`, grounded in `EVALUATION.md` (harness/coverage), `DATA_QUALITY_SPAIN_NICHE.md` (SAS, Spanish corpus, local-LLM), `README.md` (capability map) and `config.yaml` (local-LLM/Ollama/Bedrock).
- Estimated Tokens: 1300
- Dependencies: 1.1, 2.1
- Steps:
  - Row per competitor; state win and loss.
  - Collibra (+DQ): win — proof-by-execution field×article coverage vs their asserted CDE×dimension matrix; faster to evidence (no 6-month implementation); regenerable on amendment. Lose — governance breadth (CDE registry, broad connectors, enterprise stewardship), you keep Collibra for governance and layer us for the certified-rules slice.
  - Soda.ai: win — regulation grounding and article attribution (Soda has none); Spanish corpus + citations; on-prem data-egress. Lose — free Core price floor, community/public check marketplace, multi-warehouse runtime breadth.
  - Monte Carlo / Anomalo / Bigeye / Validio: win — determinism (no learned/anomaly rules), auditability per article, on-prem, SAS. Lose — unknown-unknown detection (freshness/volume/distribution), near-zero rule-authoring effort, scale/lineage monitoring.
  - Ataccama ONE (~$90K+) and Informatica: win — price and certification focus; you are not a governance platform. Lose — governance breadth, partner/connector ecosystem.
  - Stratio / Datio (local): win — no data-fabric required, focused accelerator, SAS AST differ + bilingual corpus they don't certify proof-by-execution. Lose — local brand/presence, Spanish-language sales motion, data-fabric breadth; they will out-sell on trust in Madrid.
  - OSS (Great Expectations, dbt tests + dbt-expectations, Soda Core, Elementary, Deequ): win — regulation grounding, coverage certification, Spanish, on-prem. Lose — zero price, CI-native ecosystem, no licensing friction; a consultancy could DIY rule batteries on dbt-expectations and stay cheap — this is our #1 commoditisation threat.
  - Consultancy incumbents (Management Solutions, NTT Data, Minsait, Accenture, Big 4): these are simultaneously the channel and the competitor. Win — they are the primary white-label buyer; we accelerate them and increase margin/win-rate vs their hand-written batteries. Lose — they can build their own LLM rule generator in-house and cut the accelerator if they think it is cheap to replicate.
  - Explicitly do not claim scheduler, incident-triage agent, or Anejo IX as shipped capabilities.
- Acceptance Criteria:
  - A table covering every named competitor with a concrete "we win" and "they beat us", each tied to a repo capability (with a file ref) or flagged as roadmap, never invented.

### Phase 4: Value / ROI narrative
**Goal**: The justification story for each buyer persona.

#### Task 4.1: Build the counterfactual ROI
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Per-segment ROI using only grounded numbers.
- Estimated Tokens: 800
- Dependencies: 2.2, 3.1
- Steps:
  - SI: with Collibra + human authoring, a full regulatory-evidence program is $200K–$500K/yr and slow; the certified pack matches the "prove data integrity to regulators" deliverable Collibra markets at $150K+/yr, at a fraction. Additional lever: catching reporting-submission rejections before Banco de España (EBA validation rules) avoids fix-and-resubmit cycles.
  - Consultancy: $200K–€200K–500K engagement vs (accelerator license €60K–€90K + pack fee), giving margin uplift and faster delivery.
  - Counterfactual cost: Gartner poor-DQ cost and "50% not measured" (from memo) as a framing, not a specific claim about any single bank.
  - Explicitly avoid inventing a per-bank selling value; present ranges from the memos only.
- Acceptance Criteria:
  - A small per-segment table showing our annual cost vs the counterfactual and the delta, every number traceable to a memo or marked as an assumption.

### Phase 5: Go-to-market motion
**Goal**: Which channel and how to sell.

#### Task 5.1: Confirm channel priority and partner recruitment
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Primary = consultancy white-label (Management Solutions, NTT Data, Minsait, Big 4 — pick 2–3); secondary = direct SI subscription. Position the consultancy as the front-office (they bill the bank) while we license + regenerate packs.
- Estimated Tokens: 600
- Dependencies: 4.1
- Steps:
  - Name the buyer personas: CDO / Calidad del Dato (SIs), validación interna (model risk), intervención general (Anejo IX angle); the consultancy for LSIs.
  - Define the sales collateral: the three-artifact certification (approved applicability map + zero-TODO matrix + harness run) presented as the audit pack, in Spanish.
- Acceptance Criteria:
  - A ranked channel plan and a named persona per segment, with the primary buyer for LSIs being the consultancy.

#### Task 5.2: Launch steps (ordered)
- Location: `docs/PRICING_ASSESSMENT.md`.
- Description: Actionable launch sequence.
- Estimated Tokens: 700
- Dependencies: 5.1
- Steps:
  1. Sign 1 design-partner SI (validation department) or 1 consultancy white-label; scope 4–6 weeks (per MVP_ROADMAP pilot motion).
  2. Run the pricing validation pilot (Phase 6) and measure the effort-reduction/acceptance metrics the price is anchored on.
  3. On a pass, formalise the module/tier list and publish the defensibility statement + audit-pack collateral in Spanish.
  4. Recruit 2–3 named consultancy partners with the white-label band.
  5. Land the first direct SI at module A; add the bundle at renewal.
  6. Set a go/no-go gate before any multi-region or multi-module scaling.
- Acceptance Criteria:
  - A numbered, gated launch sequence with a single go/no-go decision point.

### Phase 6: Pricing-hypothesis validation loop
**Goal**: Prove the anchor (effort reduction, acceptance, willingness-to-pay) before committing prices.
- Description: The pilot and discovery calls that validate or kill the price points; folded here because the brief makes validating the pricing hypothesis the "testing strategy".
- Estimated Tokens: 900
- Dependencies: 5.2
- Steps:
  - Design-partner pilot (one SI or one consultancy) that produces a real certified pack for GL/2017/16 and is used in a real supervisory or internal-validation conversation.
  - Measure delivery-effort reduction (baseline hand-authored vs accelerator) to confirm the 50% hypothesis; measure human-approval rate on generated checks; measure cost per pack.
  - Discovery/value interviews across 10–15 SIs and 3–5 consultancies; band willingness-to-pay with price anchors (€45K / €60K / €90K) per the two-channel model.
  - Competitor price checks: live quote Collibra+IQ, Soda Cloud, Ataccama, and a Spain consultancy day-rate sanity check.
  - Re-run the price model after metrics land; adjust any number whose anchor is falsified.
- Acceptance Criteria:
  - Pilot produces a certified pack; a recorded effort-reduction ratio; a recorded approval rate; a WTP band per segment; and a go/no-go decision on whether to keep, cut or raise the recommended prices.

## Testing Strategy

- Pricing validation is primarily a pilot + interview exercise, not code tests: the repo already has `pytest -q`, the `eval_harness.py --selftest`, and `coverage_matrix.py`, but these certify the *engine*, not the *price*. Use them to assert the claims the price rests on: run `python DQC/eval/eval_harness.py --sql <shipped_checks.sql> --fail-under 1.0` and `coverage_matrix.py --fail-under 1.0` to confirm a defensible "100% coverage" claim before it is used to justify any premium (the SOTA memo notes the recall gate is not yet pinned to 1.0 in CI — treat this as an open validation).
- Pilot acceptance criteria: (a) pack used in a real supervisory/internal-validation conversation; (b) measured time-to-certified-pack for GL/2017/16; (c) delivery-effort ratio accelerator-vs-baseline; (d) generated-check human-approval rate; (e) the pack passes a mock supervisory / audit review.
- Price sanity: run a simple Van Westendorp-style banding in discovery calls; reject any recommended price that falls outside the floor (OSS) / ceiling (Collibra-with-DQ) corridor once real data replaces memo estimates.

## Risks

- Single-regulation fragility: the product ships only GL/2017/16; the highest-value Spain demand (Anejo IX / Circular 4/2017) and the COREP/FINREP import are roadmap, not built. If the design-partner buyer needs module B, we have nothing to sell — the portfolio pricing rests on unbuilt modules. Mitigation: price module A for the pilot; only price the bundle after module B ships.
- Commoditisation by OSS / DIY: a data-office team can approximate rule generation with dbt-expectations + a prompt against a ~0.5–1 FTE cost. Our only real moat is the certification harness; if proof-by-execution isn't actually shipping at recall 1.0 in CI, we collapse into "a prompt + a catalog" and the premium is unjustified. Mitigation: wire the harness recall gate to CI (currently open per SOTA memo §6) before quoting any certification premium.
- Channel/competitor conflict: the primary channel (white-label consultancy) is also the incumbent competitor; handing the whole accelerator to Management Solutions/NTT Data/Minsait trains a future OEM and cedes the direct SI relationship. Mitigation: sell consultancies the certified pack (not necessarily the generator), or gate with per-pack royalties and a no-export/no-rebuild clause; keep a direct SI lane.
- On-prem/local-LLM double-sell risk: the data-egress advantage requires on-prem generation, but the repo notes the generation-quality ceiling is the model (Nova Micro shows this). If on-prem models can't hit the certification bar, "compliant AND high-quality" breaks. Mitigation: measure on-prem GGUF vs Bedrock recall in the pilot before selling on-prem as a premium.
- Small TAM + price resistance: ~10–15 direct accounts and ~73 LSIs is a hard revenue cap; a single premium point won't scale, and LSI budgets can't absorb €60K–€90K. Mitigation: treat this as a services-adjacent product; make the per-pack wholesale tier the LSI entry, not a platform sale.
- Anchor uncertainty: the consultancy engagement figure (€200K–€500K) and the Collibra/Ataccama prices are estimates, not live quotes; if Spanish day rates are materially lower, the €60K–€90K white-label license is too high. Mitigation: validate anchors in Phase 6 before committing.

### Self-critique
- The entire consultancy white-label price (€60K–€90K) is anchored on a €350K engagement **midpoint I estimated from a range**, and on a **claimed 50% delivery-effort reduction that the repo has never measured** — if the true per-engagement value is lower or the accelerator only saves 25%, the license is too expensive and a consultancy (which knows its own P&L) will reject it. My plan under-validates the anchor relative to how much I rely on it; the price should not be published until the pilot measures delivery-effort reduction and I re-anchor.
- I recommend the consultancy white-label as the **primary** channel while simultaneously giving those exact consultancies (Management Solutions, NTT Data, Minsait) the entire differentiator — the accelerator software — which is a textbook one-way value transfer: nothing in my plan prevents a partner from rebuilding my catalog, cutting me out after the pilot, or reselling under their brand at a price that kills my direct SI lane. It is the single biggest structural weakness and the plan must add anti-circumvention terms (sell the pack, not the generator; per-pack royalty; no-rebuild/no-export/whitelabel-limit) before the channel is prioritised.

## Rollback Plan

- If price doesn't land: ladder down — from €90K → €60K → €45K; reduce entry with a per-module/per-corpus tier; add a capped per-SI+corpus entry point; convert annual license to per-cycle pack billing so buyers pay for outcomes, not a platform.
- If white-label channel fails to stick: pivot to direct SI subscription only, making direct the primary and pricing the SI module at €45K–€60K with a fast-turnaround pack premium (€20K–€25K) for the supervisory-prompt/due-diligence wallet SIs budget for.
- If undercut by OSS in Spain: reposition away from "cheap observability/infrastructure price" to "certification + proof-for-regulator" only — shrink the deal to the annual supervisory audit-pack wallet where OSS can't compete; become the pack, not the platform; stop trying to be a data-platform.
- If a partner builds in-house: tighten the white-label terms, or drop the generator sale and sell only the certified pack (the mutation-calibrated output), licensing the harness purely as royalties.
- If the pilot cannot produce a recall≈1.0 certification run: de-market the certification claim entirely and price as a consultancy delivery-time accelerator (value = hours saved, not proof), which is a materially lower price and a narrower story.
- If the SI pilot misses its acceptance bar: do not scale; re-scope to a single corpus and single persona and re-price before re-entering.

## Edge Cases

- LSIs via consultancy (the ~73 Banco de España accounts): they buy outcomes, not platforms; price per wholesale pack €8K–€15K and let the consultancy mark up; never quote them an SI license, and ensure the wholesale price band is size-agnostic.
- Banks with hard data-egress rules (Spanish conservatism): on-prem is the selling point — but only if the local model meets the certification bar; price on-prem as a compliance-compliant premium, and if on-prem recall drops below the floor, sell hybrid (Bedrock for delta, on-prem for sensitive) and disclose the gap.
- Banks already on Collibra/Informatica: do not present as a replacement (they win on governance breadth); position as the certified-rules + audit-pack layer that complements, sold through the CDO office, priced as a module not a stack.
- Rural savings/co-ops (majority of LSIs): thin teams, standardised approach, no IRB; serve only via the consultancy per-pack; do not sell them a platform at any discount that erodes the product thesis.
- SAS-estate banks: the SAS AST differ + field-diff explainer is the hook and no observability vendor has it; price as "we speak your SAS" and use it to open the (bigger) Anejo IX / IFRS 9 conversation later.
- Bank mid-IMI (Internal Model Investigation): urgent timeline, real budget; price as a fast-turnaround premium pack, but confirm feasibility is not gated on unbuilt modules (Anejo IX risk).
- Banking groups with multiple entities (Santander, BBVA, CaixaBank): price per group with entity add-ons so the large-structure objection is pre-empted; do not price a €45K module as if it covers every subsidiary.

## Open Questions

- Confirm live prices: Collibra base ~$170K + DQ ~$156K; Soda Cloud paid tier; Ataccama ~$90K+; and a Spain-adjusted consultancy day-rate / per-engagement value (the €200K–€500K figure is an engagement estimate, not a rate card).
- Does the repo actually ship a standalone SAS AST parser + field-diff explainer? The memos assert it, but I could not locate a dedicated parser module; confirm maturity before it is used as a differentiation moat.
- Is Anejo IX / Circular 4/2017 built, or only roadmap? The current ingested corpus is GL/2017/16 only; module B feasibility and timing determine whether the bundle price is real or aspirational.
- What is the measured delivery-effort reduction and human-approval rate on generated checks in a real pilot (currently the Monte Carlo ~60% acceptance figure is industry, not ours)? This is the anchor for the whole white-label price.
- Does on-prem GGUF/Ollama meet the certification recall bar, or only Bedrock frontier models? This is decisive for the data-egress premium and for the double-sell of "compliant AND correct".
- Is the recall=1.0 gate actually enforced in CI for the harness today? The SOTA memo says it is not yet pinned to 1.0; if unresolved, the premium "100% coverage" argument is unproven.