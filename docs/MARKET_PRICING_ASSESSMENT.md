# RegLLM / DQC PoC — Market & Pricing Assessment (Spain-Only)

**Date**: 2026-09-08
**Scope**: Spanish banking niche only (~10–15 SIs + ~73 LSIs + 3–5 consultancies)
**Primary pricing model**: Consultancy white-label accelerator
**Secondary pricing model**: Direct SI subscription

---

## Overview

RegLLM/DQC occupies a **white space**: no commercial DQ or observability platform generates regulation-grounded, machine-verifiable SQL checks with article-level coverage proof. The three-artifact certification (approved applicability map ∧ zero-TODO coverage matrix ∧ 100% recall harness) is a build artifact, not a sales deck. This assessment maps the full competitor price landscape, recommends a concrete pricing architecture for the Spanish niche, articulates defensible differentiation, and supplies the ROI justification narrative.

**Headline recommendation**: Price the consultancy white-label at **€45K–€65K/year per engagement** (plus per-regulation corpus module at €12K–€18K), and direct SI at **€80K–€120K/year per institution**. This positions DQC at 10–25% of a full Collibra/Informatica stack while delivering the one thing those stacks cannot: a provable, per-article coverage audit pack. The consultancy channel is the wedge — consultancies already bill €200K–€500K per DQ-rules engagement; DQC becomes their margin multiplier.

---

## Scope

**In**:
- Full competitor price & feature mapping (Collibra, Soda.ai, Monte Carlo, Anomalo, Bigeye, Validio, Ataccama, Informatica, Stratio/Datio, OSS)
- Consultancy incumbents as pricing anchors (Management Solutions, NTT Data, Minsait/Indra, Accenture, Big 4)
- Packaging model: per-regulation corpus module, per-SI annual license, per-engagement/audit-pack for consultancies, partner pricing
- Segment pricing math with arithmetic for each buyer type
- Differentiation matrix vs every named competitor (where we win / where they still beat us)
- Value/ROI justification narrative
- Validation strategy, risks, rollback, edge cases, open questions

**Out**:
- Implementation/engineering details beyond what supports pricing claims
- Global market sizing (Spain-only focus)
- Marketing copy, brand strategy, or sales enablement materials
- Competitor financials beyond publicly reported pricing tiers

---

## Phases

### Phase 1: Competitor Price & Feature Mapping

**Goal**: Build a complete, source-grounded price and capability map of the full DQ/observability landscape as it applies to Spanish banks.

#### Task 1.1: Tier-1 pricing map (managed observability + governance suites)

- **Location**: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` (existing), `docs/DATA_QUALITY_SPAIN_NICHE.md` (existing)
- **Description**: Consolidate all publicly available pricing figures into a single comparison table. Every figure must carry a source. Flag any number that is an estimate or assumption.
- **Estimated Tokens**: 4,000
- **Dependencies**: None
- **Steps**:
  1. Extract all pricing data from the existing SOTA memo (§4) and Spain niche memo (§4).
  2. Supplement with current vendor website pricing (Monte Carlo, Anomalo, Bigeye, Validio, Collibra, Ataccama, Informatica) — note: Soda Core is free OSS; Soda Cloud pricing is not publicly listed and must be flagged.
  3. Build a comparison table with columns: Vendor, Tier, Base License, DQ Module (if separate), Implementation, Annual Total (low–high), Source.
  4. Flag all assumptions with `[ASSUMPTION: verify]` markers.
- **Acceptance Criteria**:
  - Every competitor has a row with at least a price range and source citation.
  - No price is stated without a source or an explicit `[ASSUMPTION]` tag.
  - Table covers all named competitors: Collibra, Soda.ai, Monte Carlo, Anomalo, Bigeye, Validio, Ataccama, Informatica, Stratio/Datio, OSS.

#### Task 1.2: Consultancy incumbent pricing anchor

- **Location**: `docs/DATA_QUALITY_SPAIN_NICHE.md` (§4)
- **Description**: Document the current cost structure for hand-written DQ rule batteries delivered by Spanish consultancies. This is the pricing anchor against which DQC's value is measured.
- **Estimated Tokens**: 3,000
- **Dependencies**: Task 1.1
- **Steps**:
  1. Extract the existing consultancy pricing data: €200K–€500K recurring per 3–4 person engagement, 6+ month implementation, 1–2 FTE admins.
  2. Document the specific consultancies: Management Solutions (Madrid, IRB/provisioning specialist), NTT Data (ex-everis), Minsait/Indra, Accenture, Big 4.
  3. Note the recurring nature: every circular amendment triggers re-billing.
  4. Flag: these figures are from the research memo — mark as `[ASSUMPTION: verify with industry contacts]` unless sourced from a named interview or public document.
- **Acceptance Criteria**:
  - Clear statement of current cost per engagement (€200K–€500K recurring).
  - Named consultancies and their roles documented.
  - Recurring cost driver (circular amendments) explicitly stated.

#### Task 1.3: OSS landscape assessment

- **Location**: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md` (§2)
- **Description**: Document the OSS stack (Great Expectations, dbt tests + dbt-expectations, Soda Core, Elementary, Deequ) and its real cost (engineering time).
- **Estimated Tokens**: 2,500
- **Dependencies**: Task 1.1
- **Steps**:
  1. List each OSS tool, its license cost (€0), and the engineering FTE required (0.5–1 FTE as stated in the memo).
  2. Document the gap: hand-authoring burden, no regulation grounding, coverage is whatever humans wrote.
  3. Position OSS as the "free but expensive in engineering time" alternative that DQC displaces.
- **Acceptance Criteria**:
  - Each OSS tool listed with cost and engineering burden.
  - Clear articulation of why OSS does not solve the regulation-grounded problem.

---

### Phase 2: Packaging Model & Segment Pricing Math

**Goal**: Define the pricing architecture — how DQC is packaged, what each package contains, and the arithmetic for each segment.

#### Task 2.1: Packaging architecture

- **Location**: New document or section in this assessment
- **Description**: Define four packaging tiers with explicit inclusions.
- **Estimated Tokens**: 5,000
- **Dependencies**: None
- **Steps**:
  1. **Consultancy White-Label (Primary)**: Annual license for the generator + harness. Includes: all currently-ingested regulations (GL/2017/16), the mutation-testing eval harness, the coverage matrix, SAS AST parsing, on-prem/GGUF deployment package, bilingual ES/EN output. Price: **€45K–€65K/year per engagement**.
  2. **Per-Regulation Corpus Module (Add-on)**: Each additional regulation corpus (Anejo IX, RDARR, COREP/FINREP, CIRBE/AnaCredit). Price: **€12K–€18K/year per corpus**. This is the "regenerable coverage on every circular amendment" revenue engine.
  3. **Direct SI Annual License**: Same feature set as white-label but sold directly to a Significant Institution. Price: **€80K–€120K/year per institution**.
  4. **LSI Bundle (via Consultancy)**: 10–15 LSIs served by a single consultancy engagement, bundled at a discount. Price: **€30K–€45K/year** (consultancy pays, passes through to LSIs at margin).
  5. Define what is NOT included in each tier (no scheduler, no incident-triage agent — these are roadmap items, not current features).
- **Acceptance Criteria**:
  - Four pricing tiers with explicit price ranges.
  - Each tier's inclusions and exclusions clearly stated.
  - Per-regulation corpus module pricing justified by marginal cost of corpus ingestion.

#### Task 2.2: Pricing arithmetic & defensibility

- **Location**: Same document as Task 2.1
- **Description**: Show the math for each segment and justify why the price is defensible.
- **Estimated Tokens**: 6,000
- **Dependencies**: Task 2.1
- **Steps**:
  1. **Consultancy math**: A consultancy bills €200K–€500K per DQ-rules engagement. DQC at €45K–€65K/year is 10–25% of that engagement cost. The consultancy's margin: they save 2–3 FTE-weeks per engagement (generator produces checks; human reviews instead of authors). At €150/day consultant rate, that's €30K–€45K saved per engagement. DQC pays for itself in one engagement.
  2. **SI math**: A SI with a Collibra stack already budgets $200K–$500K/yr. DQC at €80K–€120K/year is 20–40% of that, but delivers the one thing Collibra cannot: per-article coverage proof. Position as a complement, not a replacement.
  3. **LSI math**: LSIs cannot afford €80K+ directly. The consultancy bundle at €30K–€45K/year for 10–15 LSIs = €2K–€4.5K/LSI/year. This is the only viable path to the LSI segment.
  4. **OSS displacement math**: 0.5–1 FTE engineering at €60K–€80K/year = €30K–€80K/year in engineering cost. DQC at €45K–€65K replaces this entirely and adds regulation grounding.
  5. **LLM inference cost**: Single-digit dollars per generation pass on hosted models; effectively zero on GGUF/Ollama. Noise against the €45K+ licence floor.
- **Acceptance Criteria**:
  - Each segment has a clear arithmetic showing price vs. current cost.
  - Defensibility argument stated for each segment (why Collibra/Soda/OSS don't match at this price).
  - All figures carry source citations or `[ASSUMPTION]` tags.

#### Task 2.3: Partner pricing & volume discounts

- **Location**: Same document as Task 2.1
- **Description**: Define partner-tier pricing for consultancies that commit to multiple engagements or multi-year contracts.
- **Estimated Tokens**: 3,000
- **Dependencies**: Task 2.2
- **Steps**:
  1. Define a partner tier: consultancies committing to 2+ years at €55K/year get a 10–15% discount (€45K–€47K/year).
  2. Define a volume tier: consultancies serving 5+ SI clients get a per-client discount (€40K/year per additional client after the first).
  3. Define a corpus-module bundle: 3+ corpus modules at €14K each (vs. €16K standalone).
  4. State that partner pricing requires a signed NDA and a design-partner pilot commitment.
- **Acceptance Criteria**:
  - Clear partner pricing tiers with discount percentages.
  - Conditions for partner pricing stated (NDA, pilot commitment).
  - No partner price below €40K/year (floor to protect SI pricing).

---

### Phase 3: Differentiation Matrix

**Goal**: For every named competitor, state clearly where DQC wins and where they still beat us. Ground claims in actual repo capabilities — do NOT invent features.

#### Task 3.1: Competitor differentiation table

- **Location**: New section in this assessment
- **Description**: Build a row-per-competitor table with columns: Competitor, Where We Win, Where They Still Beat Us, Verdict.
- **Estimated Tokens**: 8,000
- **Dependencies**: None (but requires knowledge of actual repo capabilities)
- **Steps**:
  1. **Collibra**:
     - *Where we win*: Per-article coverage proof (field × article matrix with machine-verifiable recall = 1.0). Collibra's DQ module is ~$156K budgeted separately from the $170K base; it does CDE registries and lineage but cannot answer "show me every applicable paragraph of GL/2017/16 has a firing control." SAS AST parsing — Spanish risk teams' primary artifact. Spanish-language corpus/citations. On-prem GGUF deployment.
     - *Where they beat us*: Full governance suite (stewardship, workflow, CDE ownership). Mature ecosystem. Global brand. Multi-warehouse connectors. Incident triage. We have none of these.
     - *Verdict*: We are a complement, not a replacement. Position as the "regulation coverage layer" on top of Collibra.
  2. **Soda.ai**:
     - *Where we win*: Regulation grounding. Soda Core is free OSS; Soda Cloud is the paid tier but offers statistical anomaly detection, not regulation-derived checks. We generate SQL from regulation text with article-level attribution. SAS parsing. On-prem.
     - *Where they beat us*: Near-zero rule authoring (ML anomaly detection). Broad warehouse support. Established brand. Incident triage agents. We have no anomaly detection.
     - *Verdict*: Complementary. Soda catches unknown-unknowns; we catch known-regulation violations.
  3. **Monte Carlo**:
     - *Where we win*: Per-article coverage proof. SAS parsing. On-prem GGUF (schema never leaves the bank). Spanish corpus.
     - *Where they beat us*: GenAI monitoring agents (~60% acceptance rate). Troubleshooting/root-cause agents. Multi-warehouse. US SaaS brand. We have no incident-triage agent.
     - *Verdict*: Complementary. Monte Carlo is the "unknown-unknowns" layer; we are the "known-regulation" layer.
  4. **Anomalo**:
     - *Where we win*: Regulation grounding with article-level proof. SAS parsing. On-prem.
     - *Where they beat us*: ML checks on actual data content. No-code business-logic validation. Broad connector ecosystem.
     - *Verdict*: Complementary. Anomalo is data-content monitoring; we are regulation-derived checks.
  5. **Bigeye**:
     - *Where we win*: Regulation grounding. SAS parsing. On-prem. Per-article coverage.
     - *Where they beat us*: Automated dimension monitoring. Pre-built data quality dimensions. US SaaS brand.
     - *Verdict*: Complementary. Bigeye monitors data dimensions; we prove regulation compliance.
  6. **Validio**:
     - *Where we win*: Regulation grounding. SAS parsing. On-prem. Per-article coverage proof at a fraction of the $50K–$200K+/yr price.
     - *Where they beat us*: Managed observability at scale. Multi-source. Incident triage.
     - *Verdict*: We are the regulation-specific layer; Validio is the general observability layer.
  7. **Ataccama ONE**:
     - *Where we win*: Regulation grounding. SAS parsing. On-prem GGUF. Per-article coverage. Lower price (€45K–€65K vs. ~$90K+).
     - *Where they beat us*: Full DQ suite (profiling, cleansing, matching). Established in Europe. Multi-industry.
     - *Verdict*: We are the regulation-specific layer; Ataccama is the general DQ suite.
  8. **Informatica**:
     - *Where we win*: Regulation grounding. SAS parsing. On-prem GGUF. Per-article coverage. Lower price.
     - *Where they beat us*: Full data integration + DQ + governance. Global brand. Mature ecosystem.
     - *Verdict*: Complement. Informatica is the data integration layer; we are the regulation compliance layer.
  9. **Stratio / Datio**:
     - *Where we win*: Regulation grounding with article-level proof. Mutation-testing harness. SAS AST parsing. On-prem GGUF. Bilingual ES/EN. Regenerable coverage on circular amendments.
     - *Where they beat us*: Local Spanish brand. Datio had a BBVA alliance. Data fabric with DQ/governance. Established local relationships.
     - *Verdict*: Direct competitor in Spain. We win on regulation grounding and provable coverage; they win on local relationships and broader DQ/fabric offering.
  10. **OSS (Great Expectations, dbt, Soda Core, Elementary, Deequ)**:
      - *Where we win*: Regulation grounding. Article-level coverage proof. Mutation-testing certification. SAS parsing. On-prem. Bilingual output. One build artifact = audit pack.
      - *Where they beat us*: Free licence. Broad community. Flexible. No vendor lock-in. We require 0.5–1 FTE engineering; OSS requires the same plus regulation expertise.
      - *Verdict*: We displace the engineering time cost (€30K–€80K/yr) and add regulation grounding that OSS cannot provide.
  11. **Consultancy incumbents (Management Solutions, NTT Data, Minsait, Accenture, Big 4)**:
      - *Where we win*: €45K–€65K vs. €200K–€500K per engagement. Automated generation vs. hand-authoring. Regenerable on amendments (delta = engagement, not re-bill). Mutation-tested certification.
      - *Where they beat us*: Relationships. Full-service delivery (they provide the human review we need for applicability.yaml). Brand trust. They already have the bank's ear.
      - *Verdict*: We are their accelerator, not their competitor. They sell the audit pack; we make it 10x cheaper to produce.

#### Task 3.2: Defensible moat articulation

- **Location**: Same document as Task 3.1
- **Description**: Synthesize the six moats from the task brief into a cohesive narrative.
- **Estimated Tokens**: 4,000
- **Dependencies**: Task 3.1
- **Steps**:
  1. **Moat 1 — Regulation-grounded rule generation + machine-verifiable coverage**: The field × article matrix with recall = 1.0 is not asserted; it is proven by execution against planted defects. No commercial platform does this.
  2. **Moat 2 — Deterministic mutation-testing harness with NO LLM judge**: Recall=1.0 gate. The harness is code, not a prompt. It cannot be gaslit.
  3. **Moat 3 — Spanish-language corpus/citations + bilingual ES/EN output**: Working teams operate in Spanish; ECB JSTs read English. No US vendor provides Spanish regulatory corpus.
  4. **Moat 4 — SAS AST parsing + field-diff explainer**: SAS is the artefact Spanish risk teams live in. No observability vendor parses it.
  5. **Moat 5 — On-prem / local-LLM (GGUF/Ollama)**: Schema never leaves the bank. Data-egress compliance selling point vs. US SaaS.
  6. **Moat 6 — Regenerable coverage on every circular amendment**: Circular 1/2025 changed Anejo IX again; a corpus re-hash flips affected sections to pending and the delta becomes the engagement. Recurring revenue engine.
  7. For each moat, state what it protects against (copying, competition, commoditization).
- **Acceptance Criteria**:
  - All six moats articulated with specific evidence from the repo.
  - Each moat's competitive protection stated.
  - No capability claimed that does not exist in the repo (explicitly note: no scheduler, no incident-triage agent, single regulation so far).

---

### Phase 4: Value / ROI Justification Narrative

**Goal**: Produce the business case that a CDO or head of Calidad del Dato can take to their board or supervisory conversation.

#### Task 4.1: ROI narrative

- **Location**: New section in this assessment
- **Description**: Build a quantified ROI argument using data from the research memos.
- **Estimated Tokens**: 5,000
- **Dependencies**: None
- **Steps**:
  1. **Cost of poor DQ**: Gartner estimates $12.9M/yr average per organisation. 59% of organisations don't measure DQ at all.
  2. **Current cost**: €200K–€500K per consultancy engagement, recurring. 6+ month implementation. ROI at month 25 (for governance suites).
  3. **DQC cost**: €45K–€65K/year (consultancy) or €80K–€120K/year (direct SI). Near-zero inference cost on GGUF.
  4. **Time-to-value**: 4–6 weeks pilot (per MVP_ROADMAP.md) vs. 6+ months for Collibra/Ataccama.
  5. **Regulatory ROI**: BdE's 2025 Memoria names RDARR remediation a supervisory priority with "more intrusive" actions. EBA rejects submissions failing DPM validation rules — forcing fix-and-resubmit cycles. DQC catches rejections before submission.
  6. **Audit pack as a deliverable**: One CI command emits a versioned bundle (applicability.yaml + matrix JSON + harness JSON + git SHA). This is the "prove data integrity to regulators" deliverable that Collibra markets at $150K+/yr — here it is a build output.
  7. **Recurring revenue for consultancies**: Every circular amendment (Circular 1/2025) triggers a corpus re-hash, flipping affected sections to pending. The delta is the engagement. This is not a one-time sale; it's a recurring subscription.
- **Acceptance Criteria**:
  - ROI narrative uses only figures from the research memos or explicitly marked assumptions.
  - Clear comparison: current cost vs. DQC cost.
  - Time-to-value explicitly stated (4–6 weeks vs. 6+ months).
  - Audit pack value articulated as a regulatory deliverable.

---

### Phase 5: Go-to-Market Motion & Launch Steps

**Goal**: Define the concrete steps to validate pricing and launch in the Spanish niche.

#### Task 5.1: Design-partner pilot

- **Location**: Same document as Phase 4
- **Description**: Define the pilot structure for pricing validation.
- **Estimated Tokens**: 4,000
- **Dependencies**: None
- **Steps**:
  1. Identify 1–2 design partners: one SI (e.g., a mid-tier SI like Bankinter or Ibercaja with IRB) and one consultancy (e.g., Management Solutions or Stratio).
  2. Pilot terms: 4–6 weeks. The SI/consultancy provides a data dictionary + data extract. DQC delivers a proven check suite + audit pack for EBA GL/2017/16.
  3. Pricing test: offer the pilot at a discounted rate (€20K–€30K) in exchange for a reference case study and pricing feedback.
  4. Success criteria: the pack is used in a real supervisory or internal-validation conversation (per MVP_ROADMAP.md).
  5. Post-pilot: convert to annual license at full price if successful.
- **Acceptance Criteria**:
  - Pilot scope, duration, and pricing clearly defined.
  - Success criteria tied to actual regulatory use (not just technical validation).
  - Reference case study commitment from design partners.

#### Task 5.2: Discovery call protocol

- **Location**: Same document
- **Description**: Define the structured discovery calls to validate pricing assumptions with 5–7 target buyers.
- **Estimated Tokens**: 3,000
- **Dependencies**: Task 5.1
- **Steps**:
  1. Prepare a structured interview guide covering: current DQ spend, current tooling, pain points with regulation-grounded DQ, willingness to pay for provable coverage, data-egress constraints, existing Collibra/Informatica relationships.
  2. Target 5–7 interviews: 2–3 SIs, 2–3 consultancies.
  3. Use Van Westendorp price-sensitivity meter questions to validate the €45K–€65K (consultancy) and €80K–€120K (SI) ranges.
  4. Document findings and adjust pricing if the median "too cheap" / "too expensive" points diverge significantly.
- **Acceptance Criteria**:
  - Interview guide documented.
  - 5–7 target contacts identified.
  - Van Westendorp data collected and analyzed.

#### Task 5.3: Launch sequence

- **Location**: Same document
- **Description**: Define the 90-day launch plan.
- **Estimated Tokens**: 3,000
- **Dependencies**: Task 5.2
- **Steps**:
  1. Days 1–30: Close design-partner pilot. Begin discovery calls.
  2. Days 31–60: Complete pilot. Collect reference case study. Analyze Van Westendorp data.
  3. Days 61–90: Finalize pricing. Approach 2–3 additional consultancies with partner pricing. Target first direct SI conversation.
- **Acceptance Criteria**:
  - Clear day-by-day milestones.
  - Dependencies between phases stated.
  - Success criteria for each phase defined.

---

## Testing Strategy

**How to validate the pricing hypothesis before committing to a price point:**

1. **Design-partner pilot** (primary validation):
   - Offer the pilot at €20K–€30K (discounted) for 4–6 weeks.
   - Success = the audit pack is used in a real supervisory or internal-validation conversation.
   - Post-pilot interview: ask the design partner to rate the price on a 1–5 scale (1 = far too cheap, 5 = far too expensive). Target median = 3 (fair).

2. **Discovery call price validation** (secondary validation):
   - Van Westendorp price-sensitivity meter: four questions per respondent.
   - "At what price would you consider this so expensive you'd never buy it?"
   - "At what price would you consider this so cheap that you'd question its quality?"
   - "At what price would you start to consider it a good buy for the money?"
   - "At what price would you consider it getting expensive, but you'd still buy it?"
   - Analyze intersection points to derive optimal price range.

3. **Competitor price checks** (validation, not primary):
   - For each named competitor, verify current pricing via vendor sales contacts or public sources.
   - Flag any price that has changed since the research memo dates (2026-07-11).
   - Specifically verify: Collibra base + DQ module pricing, Ataccama ONE pricing, Monte Carlo pricing, Validio pricing.

4. **Pilot acceptance criteria** (technical validation supporting pricing claims):
   - The eval harness must pass `--fail-under 1.0` on the pilot's schema.
   - The coverage matrix must have zero TODO cells.
   - The audit pack must be generated deterministically from pinned inputs.
   - If any of these fail, the pricing claim ("provable coverage") cannot be substantiated.

---

## Risks

- **Regulatory concentration risk**: DQC currently ingests only EBA GL/2017/16. If the Spanish banking niche shifts supervisory priority to Anejo IX or CIRBE before DQC has those corpora, the value proposition weakens. Mitigation: prioritize Anejo IX corpus as the second corpus module (per MVP_ROADMAP.md §post-pilot item 4).

- **Consultancy channel risk**: If consultancies view DQC as a threat to their billable hours rather than an accelerator, they will not adopt it. Mitigation: position DQC explicitly as their margin multiplier — they bill €200K–€500K, we cost €45K–€65K, they save 2–3 FTE-weeks per engagement.

- **Price point risk — €45K–€65K may be too high for consultancies serving LSIs**: If consultancies cannot justify the spend for LSI-facing engagements (where the end client has thin DQ budgets), the consultancy channel narrows. Mitigation: the LSI bundle at €30K–€45K/year (Task 2.1) provides a lower entry point.

- **Price point risk — €80K–€120K for direct SI competes with established vendors**: A SI already budgeting $200K–$500K for Collibra + observability may not have a separate €80K+ budget line for a regulation-specific tool. Mitigation: position DQC as a complement to existing stacks, not a replacement. Bundle as "the regulation coverage layer" within the existing governance suite budget.

- **Single-regulation risk**: With only GL/2017/16 ingested, the product cannot yet serve Anejo IX compliance, which is the highest-value Spanish extension (per DATA_QUALITY_SPAIN_NICHE.md §5). A prospective buyer may say "I need Anejo IX, not GL/2017/16." Mitigation: lead with GL/2017/16 as the pilot corpus, commit to Anejo IX delivery within 90 days of first paid engagement.

- **On-prem deployment friction**: Spanish banks are conservative on data egress, but on-prem GGUF/Ollama deployment requires GPU resources and local LLM expertise that many banks lack. Mitigation: offer a managed on-prem option (we deploy and maintain the GGUF instance at the bank) as a premium service tier.

- **Self-critique #1: The €45K–€65K consultancy price is based on a single data point (the research memo from 2026-07-11) and has not been validated by Van Westendorp or any direct buyer conversation. If the actual price sensitivity median is €25K or €90K, the entire packaging model needs revision. This is the single biggest uncertainty in the assessment.**

- **Self-critique #2: The differentiation claim "no commercial platform certifies coverage against a regulation at article level" is true today but easily copyable. Monte Carlo's GenAI agents already achieve ~60% rule acceptance; if Monte Carlo or Collibra adds a "regulation coverage" module within 12–18 months, DQC's moat narrows significantly. The SAS AST parsing is a stronger differentiator (no vendor parses SAS), but it only applies to Spanish banks — a niche so narrow that a well-funded competitor could enter and dominate it. The plan does not address how to build switching costs or network effects that would protect against this.**

---

## Rollback Plan

**If the price/channel does not land, here is the fallback:**

1. **Price ladder** (if €45K–€65K is rejected by consultancies):
   - Tier 1: €25K/year — generator + harness, one corpus (GL/2017/16), no on-prem package.
   - Tier 2: €45K/year — full feature set (as currently priced).
   - Tier 3: €80K/year — SI direct license.
   - The €25K tier is a loss-leader to establish reference cases; convert to €45K after 6 months.

2. **Pivot to direct SI** (if consultancies reject white-label):
   - Sell directly to SIs at €60K–€90K/year (slightly lower than the €80K–€120K target) with a 12-month minimum commitment.
   - Target SIs that have no existing Collibra/Informatica relationship (smaller SIs, cooperative banks) where the sales cycle is shorter.

3. **Reposition vs. OSS** (if platform pricing is rejected by both SIs and consultancies):
   - Position DQC as an OSS replacement: "Stop paying 0.5–1 FTE engineering to maintain Great Expectations/dbt checks with no regulation grounding."
   - Price at €30K–€45K/year (engineering-displacement pricing).
   - Target banks where the data engineering team is already frustrated with manual DQ maintenance.

4. **Corpus-module pivot** (if the generator alone does not land):
   - Sell only the coverage matrix + audit pack as a consulting deliverable (not a software license).
   - Price: €15K–€25K per audit pack generation (per-regulation, per-bank).
   - This is a services model, not a software model — lower margin but lower adoption friction.

---

## Edge Cases

- **LSIs via consultancy**: 73 LSIs are supervised by Banco de España, mostly standardised approach, thin data teams, consultancy-dependent. They buy outcomes, not platforms. The consultancy bundle (€30K–€45K/year for 10–15 LSIs) is the only viable path. Edge case: some LSIs (tourism/cooperative banks) may have minimal IRB exposure and no need for PD/LGD checks. Mitigation: scope the LSI bundle to only those LSIs that are IRB or have provisioning exposure (Anejo IX).

- **Banks with hard data-egress rules**: Some Spanish banks may prohibit any LLM interaction (even local GGUF) with schema data, or may require air-gapped deployment. Mitigation: the GGUF/Ollama path already supports fully air-gapped deployment (no network calls). If even local LLM inference is prohibited, offer a template-based mode (no LLM, deterministic check generation from the coverage matrix) as a fallback.

- **Banks already on Collibra/Informatica**: These banks have existing budgets and relationships. DQC must position as a complement, not a replacement. Mitigation: the audit pack can be exported in formats compatible with Collibra's data catalog (JSON, CSV) and referenced within the existing governance workflow.

- **Tourism/cooperative banks**: Some LSIs (e.g., Cajamar, Cajastur) have mixed banking models (retail + tourism + cooperative). Their DQ needs may differ from pure IRB banks. Mitigation: the corpus-module architecture allows adding retail/IFRS 9 corpora (Anejo IX covers provisioning; a future retail corpus could cover consumer lending).

- **Multi-subsidiary groups**: Santander and BBVA have international subsidiaries. The Spanish niche covers Spanish entities only. Edge case: a consultancy may want to deploy DQC across multiple EU jurisdictions. Mitigation: the per-regulation corpus module architecture supports adding EBA-level corpora (not just Spanish) as separate modules.

- **Regulatory change during contract**: Circular 1/2025 amended Anejo IX. If a new circular amends GL/2017/16 during the contract year, the affected sections flip to pending and the delta becomes the engagement. This is a feature, not a bug — it drives recurring value. But the buyer may ask: "How much does a corpus amendment cost?" Mitigation: include one corpus re-hash per year in the annual license; additional re-hashes at €3K–€5K each.

---

## Open Questions

1. **What is Soda Cloud's actual pricing?** Soda Core is free OSS; Soda Cloud pricing is not publicly listed. Without this figure, the comparison table has a gap. [ASSUMPTION: Soda Cloud starts at ~$30K–$50K/year for a single warehouse — verify with vendor sales.]

2. **What are the actual day rates for Spanish consultancies?** The memo states €200K–€500K per 3–4 person engagement, but does not state the per-day rate. [ASSUMPTION: €800–€1,200/day for senior consultants, €500–€800/day for junior — verify with industry contacts.]

3. **How many of the ~73 LSIs are actually IRB or have Anejo IX exposure?** Not all LSIs will need PD/LGD checks. The addressable LSI count may be closer to 20–30, not 73. [ASSUMPTION: ~20–30 LSIs have IRB or provisioning exposure — verify with Banco de España supervisory reports.]

4. **What is the actual adoption timeline for on-prem GGUF in Spanish banks?** The data-egress argument is strong in theory, but banks may have internal policies that prohibit any LLM (even local) from processing schema data. [ASSUMPTION: 50–60% of SIs will accept on-prem GGUF — verify with design-partner conversations.]

5. **How quickly could a competitor (Monte Carlo, Collibra, or a Spanish player like Stratio) add a regulation-coverage module?** The moat is defensible today but copyable. [ASSUMPTION: 12–18 months for a well-funded competitor to build a comparable regulation-coverage feature — verify with competitive intelligence.]

6. **What is the willingness-to-pay of consultancies for a white-label accelerator?** The €45K–€65K price is based on the assumption that consultancies see DQC as a margin multiplier. This has not been validated. [ASSUMPTION: consultancies will pay €45K–€65K/year — validate via Van Westendorp in discovery calls.]

7. **Does the current single-regulation scope (GL/2017/16 only) limit the addressable market?** Banks may not adopt a tool that only covers one regulation when they need Anejo IX, RDARR, and COREP/FINREP. [ASSUMPTION: GL/2017/16 is sufficient for a pilot; Anejo IX corpus will be delivered within 90 days of first paid engagement — verify with design partners.]