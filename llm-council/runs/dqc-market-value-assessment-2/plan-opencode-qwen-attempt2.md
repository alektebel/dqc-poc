# Market & Pricing Assessment: RegLLM / DQC PoC

## Overview

RegLLM's DQC generator targets a Spanish-only niche — ~10–15 Significant Institutions, ~73 Less Significant Institutions, and 3–5 consultancies — with a fundamentally different value proposition than the generalist data-observability and governance vendors: **regulation-grounded rule generation with machine-verifiable, field × article coverage proven by execution, not assertion.** Headline recommendation: price the consultancy white-label tier at **€45K–€75K/yr per consultancy seat** (unlimited SI deployments), and the direct SI subscription at **€80K–€120K/yr base** — a 3–6× discount against the €200K–€500K per-engagement cost of hand-written rule batteries while delivering a demonstrably stronger audit pack. The defensibility rests on what is *built* (the harness, the matrix, the Spanish RAG corpus, the on-prem path) and what is *promised* (the SAS parser — a roadmap item that must ship before it can be a moat).

## Scope

- **In:**
  - Competitor price mapping across Collibra, Soda.ai, Monte Carlo, Anomalo, Bigeye, Validio, Ataccama, Informatica, Stratio/Datio, OSS (dbt, Great Expectations, Soda Core, Elementary, Deequ), and consultancy incumbents (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4)
  - Packaging model: consultancy white-label accelerator (primary) + direct SI tier (secondary)
  - Segment pricing math with arithmetic for each buyer class
  - Differentiation vs. every named competitor, explicitly bounded to capabilities the repo has today vs. roadmap items
  - Go-to-market motion for the Spain niche only
  - Validation strategy, risks, rollback, edge cases, open questions
- **Out:**
  - Engineering implementation details (how the harness refactors, how to deploy, CI configuration)
  - Global market sizing (only the Spanish/ES niche is priced)
  - Product roadmap beyond what is needed to justify pricing claims (we acknowledge SAS parser and dialect compilers as roadmap items, but do not prescribe their build plan)
  - Pricing for products outside the regulatory DQ space (general DQ platforms not serving BCBS 239 / EBA / BdE)

## Phases

### Phase 1: Competitor Price Mapping

**Goal**: Build a complete, sourced competitive price map so the recommended price points are defensible against every layer of the landscape.

#### Task 1.1: Build the three-tier + consultancy competitor matrix

- Location: `docs/MARKET_PRICING_COMPETITOR_MATRIX.md` (new)
- Description: Consolidate all known pricing into a single comparison table, distinguishing what is confirmed from the repo research memos vs. what is an assumption requiring verification. Structure the map by the three commercial tiers identified in the SOTA memo, plus a fourth "consultancy incumbent" tier.
- Estimated Tokens: 15,000
- Dependencies: None (this is a synthesis task)
- Steps:
  - Tier 1 — Managed observability: Monte Carlo ($50K–$150K to $200K+), Validio ($50K–$200K+), Anomalo (similar), Bigeye (similar). Note: all lack regulation grounding.
  - Tier 2 — OSS frameworks: Great Expectations, dbt tests + dbt-expectations, Soda Core, Elementary, Deequ. €0 licence; 0.5–1 FTE engineering (≈€60K–€120K cost/year). No regulation grounding, no audit pack.
  - Tier 3 — Governance suites: Collibra base (~€155K) + DQ module (~€143K), total governance suite €170K–€295K before services; Ataccama ONE from ~€83K; Informatica (similar tier). 6+ month implementations; ROI ~month 25.
  - Tier 4 — Consultancy incumbents: Management Solutions Madrid, NTT Data, Minsait/Indra, Accenture, Big 4. Hand-written SQL/SAS rule batteries delivered per engagement. Day rates: €200K–€500K per 3–4 person engagement, recurring on every regulatory change.
  - Local platform player: Stratio / Datio (Madrid-based, DQ/governance fabric, BBVA alliance). Pricing not publicly disclosed — mark as assumption for direct sales conversation to verify.
  - Regulatory-reporting vendors: Wolters Kluwer, Regnology. Bundle EBA validation-rule execution — not DQ observability per se, but compete for the same "regulatory data integrity" budget line.
  - Flag assumptions (not verified from public sources): Monte Carlo exact pricing, Anomalo/Bigeye/Validio exact quotes, Informatica pricing, Stratio/Datio pricing.
- Acceptance Criteria:
  - Every named competitor appears in the matrix with a price band and source
  - Assumptions are explicitly labelled
  - Matrix is reviewable by the analyst as a single page

#### Task 1.2: Identify price floors and ceilings

- Location: Same as 1.1
- Description: Establish the economic anchors:
  - **Floor:** OSS (€0 licence + €60K engineering cost) — RegLLM must cost less than building and maintaining an OSS stack with equivalent regulatory coverage.
  - **Ceiling:** Full enterprise stack (€200K–€500K/yr) — RegLLM must deliver more than just another tool in the €200K stack.
  - **Consultancy reference:** €200K–€500K per engagement is the price RegLLM competes against for consultancies — it must undercut this materially to displace hand-written batteries.
  - **SI reference:** Collibra base+DQ module (€300K) is the price RegLLM competes against for direct SI deals — it must undercut this while delivering what Collibra's DQ module does not (regulation grounding + audit pack).
- Estimated Tokens: 5,000
- Dependencies: Task 1.1

### Phase 2: Packaging Model

**Goal**: Define the packaging structure that supports the two GTM motions (consultancy white-label, direct SI) while making pricing predictable and defensible.

#### Task 2.1: Consultancy white-label packaging

- Location: `docs/MARKET_PRICING_PACKAGING.md` (new)
- Description: The consultancy is the primary channel. Positioning: "the DQC generator + harness as the consultancy's delivery accelerator."
- Packaging structure:
  - **Consultancy Seat License:** €45K–€75K/yr per consultancy (seat = right to deploy and use the generator + harness for any number of SI clients)
  - **What's included:** Full DQC generator API, eval harness with CI gates, regulation corpus modules, SAS AST parser (when shipped), audit pack generator, on-prem/GGUF deployment packaging, bilingual ES/EN output, white-label audit pack with consultancy branding
  - **Why this range:** A consultancy bills a 3–4 person engagement at €200K–€500K. A €45K–€75K seat license that enables them to deliver the same engagement 3–5× faster (reduced authoring time from weeks to days) is a 3–7× ROI. The price is also below the cost of hiring one additional senior consultant for a year (~€80K fully loaded).
  - **Price tiers within consultancy:**
    - **Basic seat:** €45K/yr — one regulation corpus module (GL/2017/16), standard harness, cloud-hosted generation
    - **Premium seat:** €75K/yr — all corpus modules, SAS parser included, on-prem deployment, priority support
  - **ARU (Annual Refresh / Update) for regulation changes:** When a circular amends a corpus (e.g., Circular 1/2025), affected `applicability.yaml` entries flip to `pending` and the delta becomes a regeneration engagement — priced as a €5K–€10K one-off per affected SI, or included in Premium seat. This is the recurring revenue engine.
- Estimated Tokens: 10,000
- Dependencies: None

#### Task 2.2: Direct SI subscription packaging

- Location: Same as 2.1
- Description: Secondary motion — selling directly to a Significant Institution.
- Packaging structure:
  - **SI Tier 1 (Standard):** €80K/yr — one regulation corpus, single SI deployment, cloud-hosted or on-prem (buyer's choice), harness access, standard support
  - **SI Tier 2 (Full):** €120K/yr — all corpus modules, on-prem mandatory, SAS parser, audit pack generation, dedicated support, BCBS 239 / RDARR governance reporting
  - **What's included vs. Collibra at €300K:** Collibra delivers governance + DQ at €300K but no regulation grounding, 6+ month implementation, 1–2 FTE admins. RegLLM delivers regulation-grounded checks with machine-verifiable coverage, deployable in 4–6 weeks (per MVP_ROADMAP.md pilot motion), 0–0.5 FTE.
  - **Why this range:** SI Tier 1 is ~60% below Collibra base+DQ module (€300K) while delivering a strictly more targeted value proposition (regulation coverage, not governance breadth). SI Tier 2 at €120K is 3× below a consultancy engagement (€200K–€500K) and delivers the same audit pack.
  - **Implementation onboarding fee (one-off):** €30K–€50K for schema onboarding (dictionary import, field × article mapping review). Waived for first 3 design-partner SIs.
- Estimated Tokens: 10,000
- Dependencies: Task 2.1

#### Task 2.3: LSI channel — light-touch pricing

- Location: Same as 2.1
- Description: ~73 Less Significant Institutions supervised by Banco de España. Most are rural savings/cooperative banks, standardised approach, thin data teams, consultancy-dependent. They buy outcomes, not platforms.
- Packaging structure:
  - **LSI via Consultancy:** No direct LSI license. LSIs access DQC through their assigned consultancy's white-label seat. The consultancy bills the LSI at €15K–€30K per engagement (vs. €200K for a full rule-battery engagement) and keeps the margin. This is a volume play — 73 LSIs at €20K each = €1.46M TAM if every consultancy distributes.
  - **Why no direct LSI price:** LSIs cannot buy at the €80K+ floor; they lack the budget and the in-house team to operate a DQ tool. The consultancy channel is the only viable path.
- Estimated Tokens: 5,000
- Dependencies: Task 2.1

### Phase 3: Segment Pricing Math

**Goal**: Show the arithmetic that makes each price point defensible vs. the counterfactuals.

#### Task 3.1: Consultancy segment economics

- Location: Same as Phase 2
- Description: Model the consultancy economics before and after DQC adoption.
- Before DQC:
  - A consultancy bids €200K–€500K for a DQ-rules engagement at 3–4 FTE × 2–3 months
  - Regulatory change triggers a re-bid at the same price
  - Delivery is hand-written SQL/SAS + Excel evidence packs
- After DQC:
  - Same engagement: €200K–€500K revenue (unchanged — the consultancy keeps the top-line price)
  - Delivery cost drops from 3–4 FTE months to 1 FTE month (generator proposes, human reviews, harness certifies)
  - Margin improvement: 50–70% on each engagement
  - Seat license cost: €45K–€75K/yr (one-time annual investment)
  - **Consultancy ROI:** A consultancy with 10 SI clients × €300K avg engagement = €3M revenue. DQC reduces delivery cost by ~€600K–€1M per year (assuming 2–3 FTE saved across engagements). Net ROI: €600K–€1M / €75K seat = 8–13× in year one.
- Estimated Tokens: 8,000
- Dependencies: Task 2.1

#### Task 3.2: SI segment economics

- Location: Same as Phase 2
- Description: Model the SI economics vs. each counterfactual.
- Counterfactual A — Collibra base + DQ module:
  - Cost: €155K (base) + €143K (DQ) = €298K/yr + €200K–€400K implementation
  - Deliverables: governance registry, DQ module checks, stewardship workflow
  - Gap: no regulation grounding, no audit pack, no SAS lineage
- Counterfactual B — OSS stack (dbt + GE/Soda):
  - Cost: €0 licence + €60K–€120K engineering time (0.5–1 FTE)
  - Deliverables: pipeline tests, anomaly monitors
  - Gap: no regulation grounding, no field × article coverage, no audit pack
- Counterfactual C — Consultancy engagement (direct hire):
  - Cost: €200K–€500K per engagement
  - Deliverables: hand-written SQL/SAS batteries
  - Gap: re-billed at every regulatory change
- With DQC SI Tier 1:
  - Cost: €80K/yr + €30K onboarding (€110K year 1, €80K recurring)
  - Deliverables: regulation-grounded checks, harness-certified coverage, audit pack, SAS lineage (when parser ships)
  - **SI ROI vs. Collibra:** €298K + €300K implementation = €598K total vs. €110K year 1. Savings: €488K year 1. Ongoing: €218K/yr savings.
  - **SI ROI vs. OSS:** €80K/yr is comparable to 0.5 FTE cost, but delivers something OSS cannot (regulation grounding + audit pack).
  - **SI ROI vs. Consultancy:** €80K/yr is 40–90% below a single engagement.
- Estimated Tokens: 10,000
- Dependencies: Task 3.1

#### Task 3.3: Total addressable market (Spain only)

- Location: Same as Phase 2
- Description:
  - **Consultancy TAM:** 3–5 consultancies × €75K avg seat = €225K–€375K/yr recurring
  - **SI TAM (SIs):** 10–15 SIs × €80K avg = €800K–€1.2M/yr recurring
  - **LSI TAM (via consultancy):** 73 LSIs × €20K avg (billed by consultancy) = €1.46M (not direct revenue, but indicates channel demand)
  - **Regeneration/ARU TAM:** 10–15 SIs × 1 corpus amendment × €7.5K avg = €75K–€112K/yr (renewable, sticky)
  - **Combined direct TAM:** €1.025M–€1.787K/yr (consultancy seats + SI subscriptions + ARU)
  - **Channel TAM (consultancy-billed to LSIs):** €1.46M — this is a market-size indicator, not revenue
- Estimated Tokens: 8,000
- Dependencies: Task 3.1

### Phase 4: Differentiation

**Goal**: State concrete, honest differentiation vs. every named competitor, bounded by what the repo has today vs. roadmap items.

#### Task 4.1: Define the six differentiation pillars

- Location: `docs/MARKET_PRICING_DIFFERENTIATION.md` (new)
- Description: Document the six pillars with evidence, explicitly calling out which are real today and which are roadmap.
- Pillars:
  1. **Regulation-grounded rule generation with machine-verifiable field × article coverage** (REAL) — The coverage_matrix.py and applicability.yaml are implemented. `--fail-under 1.0` gates CI. No commercial platform certifies coverage against a regulation at article level. This is the clearest differentiator.
  2. **Deterministic mutation-testing harness with NO LLM judge (recall=1.0 gate)** (REAL) — The eval harness (67 defects, 8 dimensions, 16 golden traces, anti-gaming measures) is fully implemented. It measures recall, coherence, specificity, and per-dimension deficiency. No vendor offers this level of certifiable evaluation.
  3. **Spanish-language corpus + bilingual ES/EN output** (REAL) — The regulation corpus is ingested in Spanish (221 paragraphs of EBA GL/2017/16 official Spanish translation). Spanish validation teams work from Spanish. ECB JSTs read English. This is a real sales advantage for Spanish banks.
  4. **SAS AST parsing + field-diff explainer** (ROADMAP — NOT IMPLEMENTED) — The SAS AST compiler, Shapley attribution, and field-diff explainer are referenced in docs and docstrings but no implementation exists. `src/sas_diff/` does not exist. This is a **critical claim** to include in differentiation, but it must be clearly labelled as a roadmap commitment, not a shipped capability. Spanish banks' IRB calibration and IFRS 9 provisioning engines are overwhelmingly SAS batch pipelines — this is where the real moat *could* be, if delivered.
  5. **On-prem / local-LLM deployment (GGUF/Ollama)** (REAL) — The multi-backend LLM client supports GGUF (llama-cpp-python), Ollama, Bedrock, Azure, LiteRT, and stub. Schema never leaves the bank when using GGUF/Ollama locally. This is a compliance selling point vs. US SaaS observability vendors.
  6. **Regenerable coverage on every circular amendment** (REAL, partially) — The hash-pinned regulation corpus means any change flips affected `applicability.yaml` entries to `pending`. The delta becomes the engagement. The mechanism exists; the operational workflow (notification, regeneration) is manual today.
- Estimated Tokens: 12,000
- Dependencies: None

#### Task 4.2: Competitor-by-competitor differentiation

- Location: Same as 4.1
- Description: For every named competitor, state where RegLLM wins and where they still beat RegLLM.
- Structure per competitor:
  - **Collibra:** Where we win: regulation grounding, audit pack, 3–6× cheaper, 4–6 week deployment vs. 6+ months, no 1–2 FTE admin. Where they beat us: governance suite breadth (CDE registry, stewardship workflow, enterprise data catalog), global brand recognition, established SI relationships (Santander and BBVA likely already have Collibra).
  - **Soda.ai (Soda Cloud):** Where we win: regulation grounding + field × article coverage vs. statistical anomaly detection, on-prem deployment (Soda Cloud is SaaS), Spanish corpus. Where they beat us: broader warehouse coverage (not limited to risk reporting), mature ML anomaly detection, established integrations, larger team. OSS Soda Core is free but lacks regulation grounding entirely.
  - **Monte Carlo:** Where we win: regulation grounding + auditable coverage vs. learned statistical rules, on-prem deployment, 3–5× cheaper. Where they beat us: ML observability maturity, GenAI troubleshooting agents, near-zero rule authoring experience, larger product surface.
  - **Anomalo:** Where we win: regulation grounding + machine-verifiable coverage, on-prem deployment, Spanish corpus. Where they beat us: data trust approach (unstructured data monitoring), ML on actual data content, broader enterprise coverage.
  - **Bigeye:** Where we win: regulation grounding + auditable coverage, on-prem deployment, cheaper. Where they beat us: statistical model maturity, broader data stack, established enterprise relationships.
  - **Validio:** Where we win: regulation grounding + auditable coverage, on-prem deployment, cheaper, Spanish corpus. Where they beat us: managed observability maturity, broader enterprise coverage.
  - **Ataccama ONE:** Where we win: regulation grounding + audit pack, faster deployment, cheaper. Where they beat us: broader DQ platform surface, global presence, more connectors.
  - **Informatica:** Where we win: regulation grounding + audit pack, faster deployment, cheaper. Where they beat us: enterprise-grade platform, massive connector ecosystem, global brand, established SI relationships.
  - **Stratio / Datio:** Where we win: regulation grounding + auditable coverage, cheaper, specific Spanish regulatory focus. Where they beat us: local presence (Madrid), existing BBVA relationship, broader data fabric platform. **Risk:** Stratio could add regulation grounding to their platform and directly compete.
  - **OSS (dbt + Great Expectations + Soda Core + Elementary + Deequ):** Where we win: regulation grounding, audit pack, field × article coverage, 0.5 FTE less engineering time. Where they beat us: €0 licence cost, broader ecosystem, community support, flexibility. **Key argument:** RegLLM costs ~€80K/yr vs. €60K–€120K engineering cost + 0.5–1 FTE + no regulation grounding. The value gap is the audit pack.
  - **Consultancy incumbents (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4):** Where we win: 3–7× cheaper for the same output, harness-certified quality, faster delivery, regeneration on amendments. Where they beat us: existing relationships, broader service portfolio, trusted advisor status. **Key argument:** We compete *with* consultancies (as a white-label tool) rather than *against* them.
- Estimated Tokens: 25,000
- Dependencies: Task 4.1

### Phase 5: Go-to-Market Motion

**Goal**: Define the concrete GTM steps for the Spain niche, prioritizing design-partner SIs and consultancy channels.

#### Task 5.1: Design-partner pilot (0–6 months)

- Location: `docs/MARKET_PRICING_GTM.md` (new)
- Description:
  - Target: 1 SI validation department (preferred: CaixaBank or Sabadell — mid-tier SIs with known IRB exposure and likely pain) OR 1 consultancy (preferred: Management Solutions Madrid — the reference IRB/provisioning consultancy)
  - Motion: 4–6 week pilot. Free access in exchange for: (a) real data dictionary + extract, (b) validation that the audit pack was used in a real supervisory or internal-validation conversation, (c) reference quote.
  - Success criteria: The audit pack is referenced in a real supervisory conversation (IMI, SREP, BdE inspection, external audit).
  - Price: €0 for pilot; convert to €45K–€75K seat (consultancy) or €80K SI tier (direct) within 90 days post-pilot.
- Estimated Tokens: 10,000
- Dependencies: None

#### Task 5.2: Consultancy channel build (6–12 months)

- Location: Same as 5.1
- Description:
  - Target: 3–5 consultancies (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4)
  - Motion: Direct sales to each. Offer early-adopter seat at €45K/yr (basic) or €60K/yr (premium). Provide: onboarding support, certification for their delivery teams, co-branded marketing.
  - Target: 2 consultancy seats converted within 12 months.
  - Revenue: €90K–€150K/yr recurring (2 seats at €45K–€75K).
- Estimated Tokens: 8,000
- Dependencies: Task 5.1 (pilot validation)

#### Task 5.3: Direct SI expansion (12–24 months)

- Location: Same as 5.1
- Description:
  - Target: 3–5 SIs (Santander, BBVA, CaixaBank, Sabadell, Bankinter)
  - Motion: Reference-driven. One pilot success → conversations with peers. Attend BdE/ECB supervisory conferences. Target: 3 SI conversions within 24 months.
  - Revenue: €240K–€600K/yr recurring (3–5 SIs at €80K–€120K).
- Estimated Tokens: 8,000
- Dependencies: Task 5.1, Task 5.2

### Phase 6: Launch Steps

**Goal**: Define the concrete pre-launch checklist before pricing is published.

#### Task 6.1: Pre-launch validation checklist

- Location: `docs/MARKET_PRICING_LAUNCH_CHECKLIST.md` (new)
- Description:
  - [ ] SAS AST parser MVP shipped (if positioning this as a differentiator — see risks)
  - [ ] Applicability.yaml for GL/2017/16: 58 pending entries reviewed and approved
  - [ ] Coverage matrix: 8 partial cells upgraded to `covered`
  - [ ] Harness recall gate enforced at 1.0 in CI
  - [ ] On-prem deployment tested with GGUF/Ollama (confirmed: schema never leaves the bank)
  - [ ] Audit pack generator produces a versioned, git-sha-bundled artifact (applicability.yaml + matrix JSON + harness JSON + git SHA)
  - [ ] Bilingual ES/EN output confirmed (corpus, citations, reports)
  - [ ] 1 design-partner pilot completed with reference quote
  - [ ] Analyst verifies: Collibra exact pricing, Stratio/Datio pricing, Monte Carlo exact pricing
- Estimated Tokens: 5,000
- Dependencies: Task 5.1

## Testing Strategy

- **Pilot validation (primary):** Run a 4–6 week design-partner pilot with one SI or one consultancy. Measure: (a) time-to-first-audit-pack (target: < 2 weeks), (b) harness recall on pilot schema (target: ≥ 0.95), (c) whether the audit pack was used in a real supervisory conversation (target: yes). This is the single highest-value validation.
- **Price sensitivity test (secondary):** Conduct 5–10 discovery calls with SI CDO office heads and consultancy delivery partners. Ask: "What would you pay for a tool that replaces a €200K–€500K consultancy engagement on DQ rules?" Record responses. If median WTP > €80K for SI, the pricing holds. If median WTP < €50K, move SI Tier 1 down to €50K–€60K.
- **Competitor price checks:** During discovery calls, ask: "What are you currently paying for Collibra/Soda/Monte Carlo?" Record and verify. Flag any discrepancy with the known figures from the SOTA memo for analyst follow-up.
- **Pilot acceptance criteria:**
  - The generated check suite covers ≥ 80% of applicable GL/2017/16 articles on the pilot's schema
  - Harness recall on pilot data is ≥ 0.85 (generous, as pilot schema may differ from eval schema)
  - The pilot team validates ≥ 70% of generated checks (indicating quality is acceptable)
  - The audit pack is produced in a single CI run
- **Anti-validation guardrail:** Do NOT proceed to paid rollout until at least one of: (a) an SI reference quote, or (b) a consultancy commitment letter. The Spain market is too small and reference-driven to justify unverified pricing.

## Risks

- **SAS parser not shipped, differentiation claim is hollow:** If the SAS AST parser and field-diff explainer (the most distinctive moat claim) are not shipped before pricing is published and sales conversations begin, the differentiation narrows significantly. The remaining differentiators (regulation grounding, harness, Spanish corpus, on-prem) are strong but overlap more with vendor capabilities than with the SAS claim.
  - *Mitigation:* Ship a minimal SAS parser (lexical-level, not grammar-perfect) before first sales conversations. Publish a public roadmap commit for the parser. In sales conversations, position it as "shipping Q3 2026" rather than omitting it.
  - **Self-critique 1:** The entire €80K–€120K SI price point rests on the audit pack delivering something Collibra's DQ module cannot. But Collibra's brand weight and existing SI relationships (especially Santander and BBVA) create a switching-cost moat that a €200K discount may not overcome. The pricing assumes banks will evaluate RegLLM as a replacement, but the reality may be "RegLLM as a supplement" — which changes the value proposition and makes €80K hard to justify as a standalone purchase. The analyst should test this explicitly in discovery calls: are SIs looking for a replacement or a supplement?
  - **Self-critique 2:** The consultancy white-label model (€45K–€75K/yr, unlimited SI deployments) assumes consultancies will adopt and distribute the tool. But consultancies like Management Solutions have deep domain expertise and may view the generator as a threat to their billing model rather than an accelerator. They may prefer to keep hand-written batteries (which they control) over a tool that reduces their FTE need. The pricing assumes a cooperative channel partner; the channel may be adversarial. A pivot to positioning RegLLM as a "consultancy-grade tool for in-house DQ teams" could face the same resistance. The analyst should validate channel appetite before publishing the consultancy price.
- **Small TAM limits pricing power:** The Spain-only niche (~€1M–€1.8M direct TAM) is small enough that a single missed SI can represent 10–15% of revenue. This reduces pricing leverage vs. larger markets.
  - *Mitigation:* Keep the price flexible. The price ladder (SI Tier 1: €50K–€120K) allows downward adjustment without restructuring.
- **LSI channel depends entirely on consultancies:** If consultancies do not distribute to LSIs, the ~73 LSI TAM is unreachable. There is no direct LSI sales motion that works at this price point.
  - *Mitigation:* This is a structural reality, not a risk per se. Accept that LSIs are indirect revenue.
- **Regulatory change is both a moat and a dependency:** The regenerable coverage feature means regulatory amendments drive recurring engagement — but if Banco de España stops amending Circular 4/2017/Anejo IX for several years, the ARU revenue shrinks.
  - *Mitigation:* Broaden corpus coverage (Anejo IX, COREP/FINREP, CIRBE/AnaCredit) so there are more surfaces for regulatory change to trigger regenerations.

## Rollback Plan

- **If the consultancy white-label price does not land (consultancies reject the €45K–€75K seat license):**
  - Move to a per-engagement licensing model: €5K–€10K per SI engagement billed through the consultancy (lower risk for consultancy, lower margin per consultancy but higher volume).
  - Or pivot to a usage-based model: €2K SI deployment + €500/check generated (only works if check volume is high and predictable).
- **If direct SI pricing does not land (SIs reject €80K–€120K):**
  - Price ladder: Step down to €50K–€60K (Tier 1) / €80K–€100K (Tier 2).
  - Or pivot to a freemium model: OSS harness + paid corpus modules (€20K/corpus/yr). This competes directly with dbt+GE and may not recover costs.
  - Or pivot to a consultancy-only model: kill the direct SI tier entirely and sell only through consultancies. This simplifies GTM but reduces TAM.
- **If neither channel lands:**
  - Reposition vs. OSS: price at €30K–€40K/yr and compete on "we do what OSS does but with regulation grounding and an audit pack." This is a survival price, not a growth price.
  - Or pivot to a services-only model: sell the generator as a custom build (€100K–€200K per implementation) with no recurring licence. This abandons the SaaS model entirely.
- **If the SAS parser does not ship on time:**
  - Remove SAS parsing from all pricing and differentiation claims. Reposition the product as "regulation-grounded DQC without SAS" — it is still valuable, but the moat narrows.
  - Communicate a public ETA for the SAS parser to maintain differentiation credibility.

## Edge Cases

- **LSIs via consultancy:** An LSI (e.g., a savings co-op) has no DQ budget but its consultancy does. The consultancy bills the LSI at €15K–€30K per engagement from its existing seat. This is free revenue for RegLLM but does not appear in direct revenue. The channel partner (consultancy) captures the margin.
- **Banks with hard data-egress rules:** Some Spanish banks (especially those with strict cloud policies) may refuse any cloud-hosted DQC generation. The on-prem/GGUF path solves this, but deployment complexity increases. Pricing does not change — on-prem is included in SI Tier 2 and Premium consultancy seat. For SI Tier 1 customers requesting on-prem, add a €10K–€15K onboarding fee.
- **Banks already on Collibra or Informatica:** These SIs have existing governance investments. RegLLM competes as a supplement (not replacement) — filling the regulation-grounding gap that Collibra/Informatica cannot. Price as a add-on: €50K–€60K/yr (discounted from €80K) with a "90-day integration trial" where RegLLM checks run alongside Collibra DQ module.
- **Banks with existing consultancy relationships:** A bank that uses Management Solutions for IRB may prefer Management Solutions to deliver DQ rules. RegLLM either becomes a Management Solutions internal tool (white-label seat) or a competing offering. In the latter case, Management Solutions may actively discourage adoption. Mitigation: position RegLLM as a consultancy-enablement tool, not a consultancy replacement.
- **Tourism/savings co-ops with thin data teams:** Some LSIs have 0–2 data engineers. They cannot operate a DQC tool even if they had budget. These institutions are fully consultancy-dependent. The only viable path is through the consultancy channel — which requires the consultancy to see value in distributing the tool.
- **Single-corpus dependency:** The product currently ships with one regulation corpus (GL/2017/16 ES). If a buyer needs Anejo IX or COREP/FINREP, those must be built first. Pricing assumes multi-corpus availability; shipping with one corpus limits the product to GL/2017/16 buyers only.
  - *Mitigation:* Add Anejo IX / Circular 4/2017 as the second corpus before pricing launches. This is the highest-value Spanish extension per DATA_QUALITY_SPAIN_NICHE.md.

## Open Questions

- **Collibra exact pricing for Spanish SIs:** The memo cites ~€155K base + ~€143K DQ module, but are these global list prices or what Spanish SIs actually pay? Enterprise discounts may reduce these significantly. *Action:* Verify through a Collibra contact or a Spanish SI procurement contact.
- **Stratio/Datio pricing and competitive posture:** Stratio is a Madrid-based platform player with a BBVA alliance. Their pricing is not publicly disclosed, and their posture toward a Spanish-only regulation-grounded DQ tool is unknown. They could be a competitor, a channel partner, or an acqui-hire target. *Action:* Direct sales conversation.
- **Monte Carlo / Anomalo / Bigeye / Validio exact pricing:** The memo gives ranges ($50K–$200K+) but these are not Spain-specific and may not reflect what Spanish SIs actually pay. *Action:* Verify through discovery calls.
- **Bank interest level:** Have any of the 10–15 target SIs expressed interest in regulation-grounded DQC? Or is this a cold-market problem? *Action:* 5–10 discovery calls with SI CDO office heads.
- **Consultancy appetite:** Have any of the 3–5 target consultancies expressed interest in a white-label DQC accelerator? Or will they view it as a threat? *Action:* Direct conversations with delivery partners at Management Solutions, NTT Data, Minsait.
- **SAS parser priority:** Is the SAS AST parser a "must-have" for sales, or can the product sell without it? If the former, how many engineering months does a minimal MVP require? *Action:* Product roadmap decision.
- **Banco de España regulatory change cadence:** How frequently does Circular 4/2017 / Anejo IX get amended? If amendments are rare, the ARU revenue engine shrinks. *Action:* Review BdE publication history for Circular 4/2017 amendments since 2017.
- **EBA COREP/FINREP validation-rule import:** EBA publishes machine-readable validation rules quarterly. Can these be imported as a generated check layer? If yes, this is a fourth corpus with regular update cadence (quarterly), strengthening the ARU case. *Action:* Evaluate EBA DPM validation rule format for automated import.