# Plan

## Overview

Position RegLLM/DQC as a Spain-focused consultancy accelerator for producing regulation-linked, execution-tested audit evidence. Recommend **€30,000/year per consultancy plus €12,000 per SI engagement**, with a secondary **€60,000/year direct-SI license**; these are proposed prices to validate, not observed market prices. Launch through paid pilots because this checkout supports generation and deterministic evaluation, but does not substantiate all the certification, SAS-lineage and amendment-automation claims in its research memos.

## Scope

- In: Spanish banking demand, the complete named competitor landscape, consultancy economics, direct-SI pricing, LSI delivery through partners, differentiation, ROI and commercial validation.
- In: A planning envelope of approximately 10–15 SI accounts, 73 LSIs and 3–5 consultancy partners. Treat these as brief/memo assumptions until reconciled by banking group against the [ECB supervised-entity list](https://www.bankingsupervision.europa.eu/framework/supervised-banks/html/index.es.html).
- In: Separate observed repository capabilities, externally sourced facts, memo estimates and proposed commercial terms.
- Out: Global market sizing, replacement of enterprise governance/observability platforms, engineering refactoring, guaranteed supervisory acceptance and pricing unavailable capabilities as delivered products.

## Phases

### Phase 1: Establish the saleable product and evidence boundary

**Goal**: Base pricing on capabilities that this checkout actually supports.

#### Task 1.1: Define the current offer and conditional differentiators
- Location: `README.md`, `docs/MVP_ROADMAP.md`, `docs/EVALUATION.md`, `DQC/eval/`, `DQC/coverage/applicability.yaml`, `src/knowledge/`, `api/routers/dqc_react.py`, `config.yaml`.
- Description: Sell a scoped, human-reviewed control-generation and evidence service before claiming a complete certification platform.
- Estimated Tokens: 1,500.
- Dependencies: None.
- Steps:
  - Use the following evidence boundary in proposals and demonstrations.

| Differentiator | Repository evidence | Commercial treatment |
|---|---|---|
| Regulation-grounded generation and field × article coverage | Spanish GL/2017/16 corpus, retrieval components, generator and coverage matrix exist. Their presence does not establish grounding for every generation route. | Demonstrate citation correctness on the exact pilot route. Sell evidence for agreed applicable obligations. |
| Deterministic mutation harness, no LLM judge | Harness exists. Read-only matrix execution returned **43/51 exact matches, 8 partial, 0 TODO: 84.31% strict coverage**. There are 58 pending review entries. | Require recall = 1.0 on the accepted test scope before releasing an accepted pack. The existing matrix gate includes partial matches and is insufficient alone. |
| ES corpus and ES/EN output | Spanish corpus and prompts exist; complete bilingual report equivalence was not established. | Include consultancy-reviewed English output as a delivery obligation, not a proven automated feature. |
| SAS AST parsing and field-diff explanation | Memos reference the larger RegLLM system; this checkout contains a SAS fixture and PROC SQL generation, but no identified AST parser/differ implementation. | Exclude from launch entitlement. Require a working demonstration before quoting it as an add-on. |
| Local GGUF/Ollama deployment | Local inference and embedding configuration exist. | Offer a bank-controlled pilot after verifying every inference, inspection, embedding and fallback path. Production on-prem packaging remains roadmap work. |
| Amendment-driven regeneration | Re-execution components exist; automated affected-cell invalidation and incremental recertification are roadmap items. | Initially sell a manually scoped amendment assessment and rerun service. |

  - State that `docs/MVP_ROADMAP.md` claims implementation in `apdq/`, but that directory is absent here. Do not repeat its completed-MVP claims.
  - Limit “no LLM judge” to the certification harness: `api/routers/dqc_react.py` separately implements an optional semantic LLM judge.
  - Define the deliverable as SQL, approved applicability, exact-reference matrix, execution results, exclusions, version identifiers and reviewer sign-off. Initially assemble the pack through consultancy delivery.
- Acceptance Criteria:
  - Every sales claim is classified as demonstrated, pilot-dependent or roadmap.
  - “Certified” means a scoped technical attestation with named human approval; it never implies regulator accreditation or complete regulatory compliance.

### Phase 2: Map pricing and competitive differentiation

**Goal**: Establish the real alternatives and avoid a misleading “cheaper Collibra” positioning.

#### Task 2.1: Maintain a competitor-by-competitor commercial map
- Location: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md`, `docs/DATA_QUALITY_SPAIN_NICHE.md`.
- Description: Use the matrix below as the initial assessment; verify quote-dependent amounts during discovery.
- Estimated Tokens: 2,500.
- Dependencies: Task 1.1.
- Steps:
  - Preserve USD memo benchmarks in USD. They are directional estimates, not verified Spanish offers or EUR equivalents.
  - Interpret “where we win” as the proposed purchasing advantage, conditional on pilot acceptance—not proof that competitors cannot implement equivalent evidence.

| Competitor | Pricing evidence | Where we win | Where they still beat us |
|---|---|---|---|
| Collibra | Memo: ~$170K base; ~$156K DQ separately; $170K–$295K governance packages before services. Scope requires verification. | A bounded Spanish regulation-to-control evidence engagement without replacing governance. | Enterprise catalog, stewardship, lineage, monitoring and established procurement. It already supports [AI-suggested SQL rules](https://productresources.collibra.com/docs/collibra/latest/Content/UnifiedDataQuality/co_about-rule-workbench.htm). |
| Soda.ai / Soda Cloud | Public Free tier; Team **$750/month**, or $9,000 annualized before additional usage; Enterprise custom. | Human-approved Spanish applicability and mutation-backed evidence, if measurably faster than building it around Soda. | Lower entry price, operational checks, collaboration and integrations. Enterprise offers private deployment. [Pricing](https://soda.io/pricing). |
| Monte Carlo | Memo: $50K–$150K/year, potentially $200K+; obtain Spain quote. | Proving agreed regulatory invariants rather than relying on anomaly detection. | Continuous data/AI observability and operational breadth. [Platform](https://montecarlo.ai/). |
| Anomalo | Memo: $50K–$150K/year, potentially $200K+; obtain quote. | Explicit article-linked test evidence for a narrow credit-risk scope. | Broad automated data-quality monitoring and detection of unexpected content problems. [Platform](https://www.anomalo.com/). |
| Bigeye | Memo category benchmark $50K–$200K+/year; no verified individual price. | Consultancy-delivered regulatory test packs with explicit exclusions. | Enterprise lineage, observability and incident workflows. [Platform](https://www.bigeye.com/). |
| Validio | Memo category benchmark $50K–$200K+/year; no verified individual price. | Deterministic tests of specified regulatory obligations. | Agentic data quality, observability and lineage across operational datasets. [Platform](https://validio.io/). |
| Ataccama ONE | Memo: approximately $90K+; verify scope and services. | Smaller, regulation-specific engagement and transparent evidence bundle. | Unified quality, catalog and observability across on-prem, hybrid and cloud. [Documentation](https://docs.ataccama.com/one/latest/overview.html). |
| Informatica | Quote required; cloud pricing is consumption-based. | A focused Spanish audit-evidence accelerator alongside existing tooling. | Integration breadth, quality/governance workflows and SAS scanning. [Pricing](https://www.informatica.com/products/cloud-integration/pricing.html), [SAS scanner capabilities](https://www.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/Advanced%20Scanners-Architecture%20Installation%20Capabilities%20and%20Updates.pdf). |
| Stratio | Spanish quote required; no defensible numeric benchmark identified. | A narrowly specified, execution-tested regulatory deliverable. | Local enterprise relationships, data fabric and existing metadata-driven rule generation. [Product explanation](https://www.stratio.com/blog/stratio-generative-ai-engine-for-enterprises/). |
| Datio | No verified standalone market price; do not assume it is an independently purchasable DQ SKU. | An external pack for a defined supervisory use case, subject to account access. | Embedded BBVA context and integration. Verify current commercial status; the [Stratio–BBVA source](https://www.stratio.com/blog/stratio-deploys-datacentric-transformation-product-with-bbva/) establishes historical origins only. |
| Great Expectations OSS | $0 license plus engineering, per memo. | Supplied regulatory interpretation and mutation evidence reduce work beyond test execution. | General-purpose validation flexibility and no license hurdle. |
| dbt tests + dbt-expectations | OSS components: $0 license plus engineering; hosted dbt services separate. | Regulatory evidence beyond developer-authored assertions. | Native analytics workflow and existing team adoption. |
| Soda Core | Free OSS; distinguish from paid Cloud. [Documentation](https://docs.soda.io/overview-main). | A reviewed domain-specific evidence package. | Local execution and inexpensive pipeline testing. |
| Elementary OSS | $0 license plus engineering; paid offerings separate. | Credit-risk applicability and article-level evidence. | dbt-oriented operational visibility and existing workflow fit. |
| Deequ | $0 license plus engineering, per memo. | Regulatory interpretation and mutation-backed controls. | Spark-native large-dataset verification. |
| SAS | No verified price in the memos. | A proposed evidence-generation layer around the existing estate. | Native execution and mature SAS lineage; parsing is not an uncontested moat. [SAS Lineage](https://support.sas.com/en/software/lineage-support.html). |
| Regnology | Quote required. | Upstream model/datamart controls and evidence before reporting submission. | Regulatory reporting production and maintained reporting infrastructure. |
| Wolters Kluwer reporting products | Quote by actual product and owner. | Upstream control evidence rather than reporting-form production. | Installed reporting capabilities. Regnology completed acquisition of its FRR business; avoid counting that business twice. [Acquisition](https://www.regnology.net/de/resources/news/regnology-completes-acquisition-of-wolters-kluwers-finance-risk-regulatory-reporting/). |
| Management Solutions | Memo’s shared consultancy benchmark: €200K–€500K per recurring 3–4-person engagement; not a verified firm quote. | Reusable generation/testing accelerator for its delivery teams. | Spanish risk expertise, interpretation and trusted client access. |
| NTT DATA | Same unverified engagement benchmark. | Faster production of a bounded regulatory rule battery. | Integration, staffing and delivery capacity. |
| Minsait / Indra | Same unverified engagement benchmark. | Reusable regulatory evidence for local delivery teams. | Spanish enterprise relationships and implementation breadth. |
| Accenture | Same unverified engagement benchmark. | Focused accelerator with measurable engagement economics. | Transformation scale and procurement access. |
| Deloitte, PwC, EY and KPMG | Same unverified category benchmark; validate each firm separately. | White-label technical evidence that supports its methodology. | Assurance relationships, reviewer expertise and institutional credibility. |

  - Treat the memo’s **$200K–$500K/year full stack** as an observability-plus-governance budget, not a Collibra-only quote.
  - Do not add Collibra’s ~$170K and ~$156K figures to the $170K–$295K range as though they describe one consistent configuration.
- Acceptance Criteria:
  - Every named competitor has pricing status, a specific proposed advantage and an acknowledged strength.
  - Remove claims that generic AI generation, private deployment or SAS lineage are exclusive to RegLLM.

### Phase 3: Set packaging and Spain-only revenue arithmetic

**Goal**: Price the consultancy’s repeatable delivery value while retaining a coherent direct offer.

#### Task 3.1: Launch a bounded commercial price card
- Location: `docs/DATA_QUALITY_SPAIN_NICHE.md`, `docs/MVP_ROADMAP.md`; proposed commercial schedule.
- Description: All following EUR amounts are recommended hypotheses, excluding VAT, infrastructure and separately scoped professional services.
- Estimated Tokens: 1,700.
- Dependencies: Tasks 1.1 and 2.1.
- Steps:
  - Adopt these initial packages.

| Package | Proposed price | Included scope and arithmetic |
|---|---:|---|
| Design-partner pilot | **€15K fixed**, 4–6 weeks | One bank, one agreed reporting pipeline, GL/2017/16 applicability and one reviewed pack. Credit once against a first-year license signed within 90 days. |
| Consultancy partner | **€30K/year + €12K/SI engagement** | White-label delivery rights, generator/harness access, GL/2017/16 module and capped enablement/support. Four engagements: €30K + 4 × €12K = **€78K**, or **€19.5K each**. |
| Partner negotiation band | **€24K–€36K/year + €10K–€15K/SI engagement** | Lower end only for prepaid volume and partner-owned first-line delivery; do not grant unlimited bank deployments. |
| LSI pack through partner | **€5K accelerator fee per scoped pack** | At ten annual packs, €30K/10 + €5K = **€8K allocated software cost per pack**. Applicable corpus required; GL/2017/16 is not automatically suitable for standardised lenders. |
| Direct SI | **€60K/year + €15K initial onboarding** | One Spanish purchasing group, GL module, one agreed pipeline scope, internal reruns and two assisted evidence releases/year. First year **€75K**. No resale rights. |
| Additional regulation module | **€15K/year partner; €20K/year direct SI** | Future Anejo IX/Circular 4/2017 module, charged only after acceptance. Partner engagement fee then covers one corpus; each additional corpus-specific pack adds **€5K**. |
| Amendment-only engagement | **€5K partner fee** | Material change within one previously accepted corpus/pipeline; routine reruns and error corrections remain included. Major scope expansion becomes a new engagement. |

  - Define an engagement as one named bank, corpus, pipeline scope and accepted evidence baseline, with corrective reruns included for 90 days. A partner license never authorizes permanent unrestricted generator use by client banks.
  - Permit banks to retain and execute delivered SQL and archived evidence after expiry; renewal purchases generation, maintenance and support.
  - Treat the €30K partner base as €20K engine/enablement plus €10K GL corpus maintenance; the €60K direct license as €40K engine/support plus €20K GL module. These are pricing allocations, not measured cost accounting.
  - Use Spain-only scenarios: three partners with four engagements each yield **3 × €78K = €234K** annual vendor revenue, of which €90K is contracted base and €144K depends on engagement volume. Two non-overlapping direct SIs add **€120K recurring**, producing **€354K** before onboarding.
  - At €60K each, 10–15 direct SI buyers imply **€600K–€900K** theoretical annual license revenue at complete penetration—not a forecast. Seventy-three LSIs × €5K gives **€365K** only if every LSI purchases one eligible pack annually; current corpus fit does not support that assumption.
- Acceptance Criteria:
  - Forecasts separate recurring commitments, engagement revenue, services and downstream bank expenditure.
  - Deduplicate SI groups, shared-service LSI buyers and channel/direct opportunities; never sum overlapping saturation scenarios.
  - No unavailable corpus, SAS parser or automated amendment feature is invoiced as delivered.

### Phase 4: Establish a defensible ROI narrative

**Goal**: Justify the price through measured labour savings and evidence quality.

#### Task 4.1: Use buyer-specific economic cases
- Location: `docs/DATA_QUALITY_INDUSTRY_SOTA_2026.md`, `docs/DATA_QUALITY_SPAIN_NICHE.md`; pilot time records.
- Description: Compare like-for-like authoring, review and evidence work, rather than claiming savings against an entire platform or engagement.
- Estimated Tokens: 1,100.
- Dependencies: Task 3.1.
- Steps:
  - Present consultancy economics using explicit assumptions: 100 days saved × €600 loaded internal cost/day = **€60K gross capacity value**. Subtract €19.5K allocated license/engagement cost and €10K incremental adaptation/review cost: **€30.5K net value**, or **103% ROI** on €29.5K incremental cost.
  - State the break-even requirement: €29.5K/€600 = **49.2 saved days**. Redeployed staff create value only if capacity becomes billable or avoids hiring; they are not automatically cash savings.
  - Present direct-SI economics: 150 saved days × €800 buyer-validated avoided cost/day = **€120K benefit**. Against €75K first-year fees plus €20K bank-side effort/infrastructure, net benefit is **€25K**, approximately **26% ROI**. Break-even is **118.75 days**; at 75 saved days, the proposal loses €35K.
  - Explain that €19.5K is approximately **3.9%–9.75%** of the memo’s €200K–€500K engagement fee, but engagement revenue is not addressable labour cost.
  - Against Collibra, sell incremental regulatory evidence without replacing governance. Against Soda’s $9K annualized Team entry point and free OSS, justify the premium entirely through reduced interpretation, authoring and evidence-preparation effort.
  - Use the narrative: “Your team approves what applies; every accepted control comes with reproducible evidence of what it detects, its citation and its exclusions. The consultancy retains judgment and sign-off.”
- Acceptance Criteria:
  - Every ROI model includes review, adaptation, infrastructure and recurring support.
  - Exclude avoided fines, generic global poor-data-quality estimates and unmeasured capital benefits.

### Phase 5: Execute the channel motion and launch gates

**Goal**: Secure repeatable Spanish demand before expanding scope.

#### Task 5.1: Convert pilots into evidence-led partner sales
- Location: `docs/DATA_QUALITY_SPAIN_NICHE.md`, `docs/MVP_ROADMAP.md`; proposed pilot brief and partner schedule.
- Description: Lead with a consultancy delivery partner and one SI validation sponsor.
- Estimated Tokens: 1,200.
- Dependencies: Tasks 1.1–4.1.
- Steps:
  - Weeks 1–2: prepare a Spanish sample pack, English summary, capability boundary and the €15K pilot statement of work. Identify buyers in Calidad del Dato, validación interna and financial reporting.
  - Plan discovery with three consultancy practice leads, three SI sponsors and two LSI/shared-service buyers. Seek access and contacts through the user’s authorized commercial process; this assessment does not send outreach.
  - Weeks 3–8: run one partner-led SI pilot against an agreed manual baseline; compare similar obligations and record all reviewer corrections.
  - Weeks 9–12: offer the €30K partner commitment after acceptance. Require a second named opportunity before granting volume discounts; use non-exclusive agreements and account registration to manage channel conflict.
  - Make Anejo IX the first expansion only with a funded sponsor. Circular 1/2025 genuinely amended Circular 4/2017, including Anejo 9, providing a concrete historical amendment case; verify applicable provisions and effective dates for each bank. [BOE text](https://www.boe.es/buscar/doc.php?id=BOE-A-2025-26847).
  - Sell amendment work as impact identification, approved changes and rerun evidence. RDARR/BCBS 239 governance obligations require separate ownership/process evidence; SQL cannot certify them alone.
- Acceptance Criteria:
  - Launch requires one paid accepted pilot, one proposed annual conversion and one documented repeat-engagement opportunity.
  - Consultancy compensation remains tied to interpretation, integration and accountable review, reducing incentives to reject automation merely to preserve authoring hours.

## Testing Strategy

- Validate willingness to pay through signed paid-pilot terms and subsequent purchase decisions; discovery enthusiasm is insufficient.
- Obtain comparable Spanish quotes or anonymised invoices for Collibra, Soda Enterprise and at least one incumbent consultancy. Record date, modules, deployment, services, usage limits, tax and contract duration.
- Require approved applicability, **zero partial/TODO cells**, recall **1.0 overall and by applicable article/dimension**, successful clean-data checks and resolution of decoy/overbroad flags for the accepted pilot scope.
- Add reviewer-authored holdout defects and a second bank/schema before asserting repeatability. A harness self-test validates oracles, not the generator’s performance or regulatory completeness.
- Require correct citations and equivalent ES/EN meaning on all accepted pilot controls; record non-testable obligations explicitly.
- Verify local-only operation under blocked external networking, including inspection, embeddings, logging and fallback behaviour.
- Commercial pass: at least 30% reduction in measured combined authoring/review/evidence effort, plus positive buyer-specific ROI at the proposed price.
- Measure vendor support effort and contribution margin. Decline fixed-price production commitments where adaptation costs remain unbounded.
- This assessment executed the read-only coverage calculation; it did not establish a passing generated-check recall result or run a live bank pilot.

## Risks

- **Self-critique:** The €30K/€12K/€60K prices are reasoned hypotheses without observed Spanish willingness-to-pay evidence. One sponsor could accept a pilot yet reject annual licensing; require conversion evidence before budgeting recurring revenue.
- **Self-critique:** The consultancy ROI assumes 100 saved days and repeat use across four engagements. Neither is demonstrated; manual schema mapping and regulatory review could consume the entire saving.
- **Self-critique:** The proposed moat is incomplete in this checkout: 84.31% exact matrix coverage, pending approvals and absent SAS/APDQ components weaken premium positioning. Restrict claims and charge initially for a bounded assisted pilot.
- **Self-critique:** The competitor map cannot establish absence of equivalent article-level testing in private enterprise implementations. Validate with demonstrations and procurement evidence; avoid “no competitor can do this.”
- Channel partners may prefer billable manual work or build internally. Target fixed-fee delivery pressure, establish reusable methodology ownership and demonstrate incremental margin.
- A handful of Spanish buyers creates concentration and long procurement cycles. Keep fixed costs aligned with signed commitments and avoid exclusive channel dependence.
- Private deployment is not unique: Soda, Collibra and Ataccama offer relevant options. Differentiate the complete evidence workflow, not vendor nationality.
- Synthetic recall does not prove production completeness or supervisory acceptance. Maintain explicit scope, holdout tests and independent regulatory review.
- Corpus updates create expert-maintenance costs and liability. Fund expansion separately and define who approves changed interpretations.

## Rollback Plan

- If two qualified buyers reject the annual commitment after successful pilots, offer **€15K–€20K standalone packs** with limited reruns; defer subscription until repeat demand is demonstrated.
- If price is the objection and ROI remains positive, use the defined **€24K base/€10K engagement floor** only for reduced support or prepaid volume.
- If partners do not convert within 90 days of pilot acceptance, prioritize direct SI buyers at €60K; test a **€40K narrow tier** limited to one evidence release and reduced support.
- If OSS is preferred, reposition as regulatory applicability, mutation-library maintenance and evidence preparation around the bank’s existing execution stack.
- If quality or deployment gates fail, retain the previous approved SQL/evidence baseline, withdraw the failed release and revert to consultancy-authored controls.
- Preserve previously delivered artifacts and contractual rights. Reprice only renewals or new scope; do not retroactively charge for promised pilot functionality.

## Edge Cases

- **LSIs via consultancy:** Confirm regulatory applicability first. Standardised lenders may need Anejo IX rather than the current GL/2017/16 offer; defer unsupported work.
- **Hard data-egress restrictions:** Require verified local operation and bank-approved installation/support arrangements; local inference configuration alone is insufficient.
- **Existing Collibra/Informatica estate:** Deliver complementary SQL and evidence for customer-managed ingestion. Do not promise ready-made connectors or platform replacement.
- **Tourism exposure:** Treat tourism as portfolio context requiring validated segment-specific assumptions, not a separate regulated institution category.
- **Savings/rural cooperatives:** Price against the actual purchasing or shared-service group; cooperative members do not necessarily represent independent licenses. Avoid double-counting Cajamar.
- **Cross-border SI groups:** Limit the initial agreement to Spanish scope even when the parent operates globally.
- **Multiple consultancies at one bank:** Register engagement scope and evidence ownership to prevent duplicate charging and conflicting attestations.
- **SAS-heavy production:** PROC SQL generation and SQLite evaluation do not prove native SAS execution equivalence; require bank-side validation before acceptance.
- **No material amendment in a year:** Subscription value must also come from schema/control changes and repeat validation; do not assume guaranteed annual amendment revenue.

## Open Questions

- Current deduplicated Spanish SI/LSI buyer counts and shared-service purchasing structures remain unverified.
- Spanish negotiated competitor prices, actual consultancy labour costs and the rule-authoring share of engagements remain unverified.
- Partner willingness to pay for white-label rights, versus building internally, remains unverified.
- Bank acceptance of the proposed technical attestation and required independent signatory remain unverified.
- Production availability and licensing of the larger RegLLM SAS/APDQ components remain unverified.
- Repeatable adaptation effort, bilingual review cost and local-deployment support cost remain unverified.
- Demand for Anejo IX is plausible from the memo, but a funding sponsor and accepted corpus scope are still unconfirmed.