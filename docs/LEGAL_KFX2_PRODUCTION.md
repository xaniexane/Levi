# KFX² on the legal AI giants — Harvey, CoCounsel (Thomson Reuters)

Date: 2026-09-21. Workstream 12 of 13. LIGHTER PASS — capability, not a product.

## HARD BOUNDARY (read first)

LEVI legal proficiency is a **capability**, never a law practice. It will
never claim to give legal advice, never claim attorney-equivalent
competence, and every legal workflow terminates in a **consult-a-licensed-attorney handoff**.
Unauthorized-practice-of-law (UPL) risk is a flagged gate, not a detail.

## (a) Competitor teardown

Research via public secondary sources only (browser search, 2026-09-21).
Everything below is as-stated by third parties unless noted; nothing was
invented. Official primary pricing pages for either product could not be
verified this pass — marked below.

### Harvey AI (harvey.ai)

**What it is:** Generative AI legal assistant built for elite law firms,
backed by the OpenAI Startup Fund. Serves Am Law 100 firms and Big Four
accounting firms (e.g., PwC, per third-party profiles). CEO: Nikki Shaver
(per Legal TechHub/Pulse briefing, 2026).

**Capabilities (as stated by third-party reviews):**
- **The Assistant** — conversational legal Q&A with citations; analyzes up
  to ~50 documents at once; drafts memos.
- **Vault** — secure enterprise document repository; per the 2026 Pulse
  briefing it can ingest and OCR up to 100,000 files per project and query
  across internal plus external sources (e.g., LexisNexis).
- **Workflow Builder / Agent Builder** — no-code "words to workflows"
  automation; pre-built legal AI agents (500+ use-case agents reported
  live in 2026) covering due diligence, litigation prep, regulatory
  tracking.
- **Source Assured™** — direct links to the clauses/case law/statutes used
  in an output (hallucination control via transparency).
- **Model-agnostic orchestration** — per Pulse: up to ~100 model calls per
  query, selecting the best model per lawyer-validated benchmarks.
- **Governance controls** — client-matter numbers required per query,
  matter blacklists, audit trails, track-changes drafting, Word/Outlook
  integration, shared firm-client workspaces ("Shared Spaces").
- **Custom Legal LLMs** — models tailored to a firm's own precedents and
  knowledge base. SOC 2 Type II certified, per third-party claims
  (unverified from a primary source this pass).

**Pricing:** Official pricing page could not be verified this pass.
Harvey's model is described across sources as **custom enterprise pricing,
quote-only, no publicly listed rates**. One third-party affiliate-style
source (is4.ai) claims "~$10,000/month for firms with 50+ attorneys" —
**unverified**; treat as hearsay, not a number we can act on. No official
per-seat price could be found.

**What firms love (third-party testimonials — treat as vendor/affiliate
marketing, unverified):** large contract-review time cuts (one partner
claim: 55% reduction; another: 40-hour due diligence → 4 hours).

**What firms hate / the friction:** smaller or less-resourced teams find
it inaccessible — the enterprise pricing and implementation requirements
assume dedicated tech resources and substantial legal-AI spend (per a
GitHub-hosted comparison doc). The whole thing is BigLaw-first; solo and
small-firm lawyers are priced out and scoped out. Vendor marketing is also
the only public evidence of quality — no independent accuracy benchmarks
were found this pass.

### CoCounsel / Casetext (Thomson Reuters)

**What it is:** The AI legal assistant built by Casetext (first GPT-4
legal assistant, launched March 2023), acquired by Thomson Reuters in
August 2023 for **$650 million** in cash (per acquisition reporting).
Now the AI engine across TR's legal stack (Westlaw, Practical Law,
CoCounsel Legal). Per Reuters (2026-02-24): ~1 million CoCounsel users.

**Capabilities (as stated):**
- Natural-language legal research across 50+ jurisdictions with
  **Westlaw-backed citations** — the key differentiator: citations are
  pulled from the actual Westlaw database, which materially reduces
  hallucinated-citation risk vs. pure generative answers (per AI Vortex
  review, 2026).
- Document review, contract analysis, deposition prep, timeline creation
  from document sets, contract policy-compliance review.
- **CoCounsel Legal** (announced Aug 2025, agentic AI platform) plus the
  "final version" of Westlaw: complex legal research, document
  summarization, privacy assessment, courtroom analysis, contract
  analysis, topic research.
- TR claims: 99.9% accuracy in legal-citation verification (vendor claim —
  unverified); early testers "62% faster" and 3.2 hours saved per search
  (vendor claim — unverified).
- Distribution: bundled with Westlaw subscriptions or standalone.

**Pricing:** Official pricing could not be verified this pass.
Described as **seat-based, bundled with Westlaw or standalone**. One
third-party source (is4.ai) claims **$500–$700/user/month depending on
firm size** — **unverified**; do not treat as fact. One source mentions a
7-day free trial at casetext.com/cocounsel (unverified this pass).

**What firms love:** the Westlaw citation layer — when it cites, it's
citing the real database, and lawyers trust that. Research speed for
verified authorities.

**What firms hate / the friction:** the Westlaw connection is also the
trap — per AI Vortex (2026), it locks firms deeper into the Thomson
Reuters ecosystem ("very high" lock-in risk). Deposition-prep and timeline
features are newer and **less proven**: they reportedly work on clean,
structured sets and struggle with messy productions, needing heavy
editing. The moat is the content library — 175 years of proprietary,
editorially-enhanced content, much of it undigitized and unavailable
publicly (per TR executives to Reuters) — i.e., a moat no new entrant can
buy into, but also a moat that means **everything must live inside their
cloud**.

### Cross-competitor pattern (the important part)

1. **Per-seat enterprise pricing** — both gate on money and firm size.
2. **Cloud document harvesting** — your privileged documents go to their
   servers, guarded by "SOC 2, trust us."
3. **Black-box answers** — both bolt on citation-transparency features
   precisely because the underlying answers are opaque generative output.
4. **Ecosystem lock-in** — TR's moat is the content you can't leave;
   Harvey's moat is the custom model your firm trained on their cloud.
5. **BigLaw-first** — solo practitioners, small firms, and ordinary owners
   are not the customer.

## (b) KFX² — absorb, reverse, amplify, return unreplicable

### ABSORB — their patterns worth taking

1. **Citation-backed answers.** Their Source Assured™ / Westlaw-backed
   citations are the right instinct: never an unsupported assertion.
   We adopt it as physics: *every* legal-capability output carries
   source pointers or says explicitly what it cannot source. (We will
   never have Westlaw's 175-year proprietary corpus; we don't pretend to.
   Our pointers cite the user's own documents and public sources only.)
2. **Clause extraction / obligation tables.** Contract analysis (clauses,
   risks, deviations from standard terms) is a genuine capability shape.
   We adopt the shape as a local document-understanding routine.
3. **Repeatable workflows.** Their "words to workflows" builder is
   automation of checklists. We adopt the shape as deterministic
   playbooks — the same checklist, every time, auditable line by line,
   no model-call roulette underneath.
4. **Drafting with track-changes semantics.** They draft with version
   history and edit-in-place. We adopt drafts-as-diffables, not
   drafts-as-deliverables.
5. **The attorney-review gate.** Every honest implementation step in both
   products ends with "all AI-generated work must be verified by a
   licensed attorney." We adopt this — not as a footnote, but as the
   **terminal gate of every legal workflow**. This is canon now: a legal
   capability workflow does not *finish*; it *hands off*.

### REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Per-seat enterprise pricing; solos priced out | No per-query model cost in our architecture (stdlib + local brain + owner's own files) → no per-seat meter exists to charge |
| Privileged documents harvested to their cloud | Documents never leave the machine — local-first is physics, not policy |
| Black-box generative answers with bolted-on transparency | Deterministic routines + explicit "I cannot source this" — honesty by construction, not by link |
| Westlaw ecosystem lock-in | No ecosystem to lock into; works on the owner's own documents, in the owner's formats |
| BigLaw-only scope; the rest of the world unserved | One owner, one machine — the individual and the small firm are the *first* customer |
| "Trust us, we're SOC 2" confidentiality | Confidentiality as architecture: there is no server to subpoena, no training pipeline to leak into |
| Citation hallucination risk in pure generative tools | Research workflow points at real retrieved text; citations are pointers to text the owner can open |

### AMPLIFY — strengths made unreplicable

Their cloud legal AI gives citation-backed speed on their database.
**Our local counsel-desk gives the confidentiality story no cloud vendor
can ever tell:**

- **"The privileged document never leaves the machine" is a physical
  fact, not a policy.** Their confidentiality is a promise about a
  server; ours is a property of the architecture. A law firm cannot ask
  Harvey for this — it would destroy how Harvey eats.
- **The attorney handoff is structural.** Their workflows end in a
  deliverable the lawyer *should* check. Ours end in a handoff packet —
  the workflow cannot be marked done until a licensed attorney is named
  as reviewer. The gate is the product shape.
- **No marginal query cost → no metering → no per-seat logic.** Their
  entire pricing structure (per-seat, bundled, quote-only enterprise)
  exists to pay for *their* cloud-model architecture. Our architecture
  doesn't have those costs, so it doesn't have those punishments —
  same KFX² logic as the companion lanes.
- **The owner's own corpus is the moat.** Their moat is 175 years of
  proprietary content; ours is the owner's private precedent pile,
  journals, contracts, and notes — the corpus that must never touch a
  cloud, and now never has to. Nobody else can build on it because
  nobody else is allowed to have it.
- **Deterministic playbooks over agentic black boxes.** Their agents fire
  ~100 model calls per query; ours runs the same auditable checklist
  every time. When stakes are high and explanations are owed (as in
  legal work), determinism is the feature.

**Return to sender:** everything they monetize through gatekeeping
(enterprise seats, Westlaw bundles, custom-model training on their
cloud) we ship as local capability — because our physics made the
gatekeeping unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what the legal AI giants do, what
they don't, and do it even better, and for fraction of fractions —
feature-for-feature parity PLUS their gaps, better built, at radically
lower prices. Dollar-scale entry, volume over margin. This is the
positioning law for every production plan, and this capability is no
exception — with the hard boundary above unchanged: a capability, never
a law practice, every workflow terminating in the attorney handoff.

**Parity — what we match feature-for-feature.** Citation-backed answers
(their Source Assured™ / Westlaw-backed citations, adopted as:
every output carries source pointers or says what it cannot source);
clause extraction and obligation tables from contracts; repeatable
workflows (their "words to workflows," adopted as deterministic,
auditable playbooks); drafting with track-changes semantics
(drafts-as-diffables); and the attorney-review terminal gate that every
honest legal-AI workflow already demands. Nothing in the competitor
capability shape is missing from the slate.

**Exclusives — what they don't offer.** The privileged document never
leaves the machine — confidentiality as architecture, not a SOC 2
promise; the attorney handoff is structural (no workflow can be marked
done until a licensed attorney is named as reviewer); no per-query
model cost, so no per-seat meter exists to charge; the owner's own
corpus is the moat — the private precedent pile that must never touch
a cloud, now never has to; deterministic checklists instead of ~100
model calls per query. BigLaw-first pricing and cloud harvesting are
their physics; the individual and the small firm are our *first*
customer.

**Price as a fraction of theirs.** Their pricing is custom enterprise,
quote-only, per-seat — and this pass could not verify any official
number for either product. The is4.ai claims (~$10,000/month for Harvey
at 50+ attorneys; $500–$700/user/month for CoCounsel) are explicitly
marked unverified hearsay in this document. Our price anchor: there is
no per-seat meter in our architecture (stdlib + local brain + the
owner's own files), so the BigLaw pricing structure has nothing to
charge against. The doctrine's dollar-scale-entry promise holds because
the marginal cost is zero — margin comes from volume of owners served,
not seats sold.

## (c) PRODUCTION-PHASE PLAN

Capability name in repo terms: **counsel-desk** (a capability inside
LEVI, stdlib-only, local-first — nothing in this plan changes that).

### Sequence (each stage ships behind the attorney-handoff gate)

**Stage 1 — Document ingestion (offline).**
- Plain-text/document intake of the owner's own legal-ish documents:
  contracts, leases, NDAs, notices. stdlib parsing (text, markdown,
  basic PDF extraction); OCR via system tools if present, honestly
  labeled by quality.
- Local vault: 0600-permission storage, indexed for retrieval, never
  synced anywhere. This is our Vault — theirs holds 100,000 files per
  project on their cloud; ours holds the owner's corpus on their disk.
- Milestone: intake → local index → retrieval of a clause by query,
  all offline. Test: zero network calls during the whole run.

**Stage 2 — Clause extraction / obligation tables (deterministic).**
- Clause finder (pattern-based, auditable): parties, dates, payment
  terms, termination, indemnity, confidentiality, renewal, notice
  windows.
- Obligation table output: who owes what, by when, with pointers to
  the exact source text span.
- Milestone: fixture contracts produce obligation tables with every
  row traceable to a quoted span. No row without a quote.

**Stage 3 — Plain-language document explainer (traceable).**
- Line-by-line and section-by-section explanation of what a document
  *says* — with the hard rule: explaining a document is not giving
  legal advice. The explainer states what the text contains and flags
  what it *cannot* assess (applicability, enforceability, strategy).
- Every explanation carries the attorney-handoff reminder and a
  "consult a licensed attorney" packet seed.
- Milestone: explainer output on a fixture NDA, reviewed against a
  lawyer-drafted reference for completeness and over-claiming.

**Stage 4 — Research workflow (owner's corpus + public sources).**
- Query → retrieve from the owner's own corpus and public legal
  sources the owner provides. Citation formatting, source pointers.
- Hard honesty: **we do not have Westlaw/LexisNexis** and never claim
  coverage comparable to theirs. Unknown = "not in the available
  sources," stated outright.
- Milestone: end-to-end research question → sourced answer → handoff
  packet, all with named sources or explicit gaps.

**Stage 5 — Deterministic legal playbooks.**
- Repeatable checklists: contract first-pass review, document intake
  checklist, deposition-prep document organization, matter closeout
  checklist. Same inputs → same checklist, every run.
- This is the reversal of their "words to workflows" — our playbooks
  are code the owner can read, not prompts the vendor can change.
- Milestone: three playbooks green against fixture inputs; a sibling
  worker can run one without talking to us.

**Stage 6 — Attorney-handoff packet.**
- Every capability emits a packet: what was analyzed, source spans,
  what was NOT assessed, the explicit "this is not legal advice" block,
  and a named-attorney field that must be filled before the workflow
  is marked complete.
- Milestone: packet schema ratified; no legal workflow can report
  completion without a handoff target.

### Gated on Chauncey

- **Accuracy sign-off.** No capability ships to the owner's hands until
  he has reviewed fixture outputs (especially Stage 3 explainer and
  Stage 4 research) — per the everything standard: outputs re-read,
  honest verdict, nothing ships until it's actually right.
- **Wording of the not-legal-advice block.** His word settles the exact
  language; it is a legal-exposure surface, so it doesn't get invented
  by a worker.
- **Any licensed legal-content integration.** If we ever license any
  legal database or content feed, that's his decision with his five
  specifics (destination, scope, account, copy, terms).
- **OCR/system dependencies.** Any non-stdlib dependency introduced
  for document parsing needs his word per the stdlib-only kernel law
  (waiver or rejection — his call).
- **Any external release.** As always: publication holds; push needs his
  fresh word.

### Hard nos

1. **No legal-advice claims.** The capability explains documents and
   organizes information. It never advises, never strategizes, never
   predicts outcomes, never says what the owner *should* do.
2. **No attorney-equivalent competence claims.** No "digital associate,"
   no "like a lawyer." Capability language stays capability-sized.
3. **No UPL exposure.** The attorney handoff is structural, not
   cosmetic — a workflow without a named attorney reviewer is
   incomplete by definition.
4. **No real-matter filing or signing automation.** Drafts are drafts;
   anything that touches a live matter waits for the attorney.
5. **No cloud fallback for legal documents.** Privileged material never
   leaves the machine for a model API, an embedding service, or a
   hosted OCR endpoint — the local-only property is physics, and
   breaking it breaks the entire unreplicable story.
6. **No Westlaw/Lexis equivalence claims.** We name exactly what sources
   we have and what we don't.
7. **No invention.** Capabilities, pricing, and sentiment in this doc
   are as-stated-by-others and unverified; the build makes no claims
   the repo can't prove.

## Honest limits of this pass

- Neither Harvey's nor CoCounsel's official pricing could be verified
  from primary sources; all pricing figures are third-party claims
  explicitly marked unverified.
- Firm sentiment comes from vendor testimonials and affiliate-style
  reviews — useful as pattern signal, not as evidence.
- No independent accuracy benchmarks for either product were found.
- This is a docs-only plan. No code, no commits, no capability yet
  exists — `core/levi/` has no legal domain today.
