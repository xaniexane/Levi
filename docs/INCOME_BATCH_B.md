# INCOME Batch B — Content Engines (slots 21–32)

Twelve original, stdlib-only, deterministic content-assembly generators.
Zero cost to run (local CPU only, no network, no APIs, no LLMs). Each one
takes structured input via params and assembles a real deliverable document
— template/assembly logic, honest output, no generated filler pretending
to be insight.

## The generators

| Slot | ID | Name | Entry | Does |
|---|---|---|---|---|
| 21 | `newsletter-drafter` | Newsletter Drafter | $3.00 | Topic bullets → full newsletter draft: numbered sections, tagline, CTA block, footer. Outputs `.md` + `.txt`. |
| 22 | `changelog-composer` | Changelog Composer | $2.00 | Structured change entries → formatted changelog, grouped by type (added/fixed/security/…), Keep-a-Changelog style. Outputs `.md` + `.json`. |
| 23 | `product-description-forge` | Product Description Forge | $4.00 | Spec sheets → benefit-led copy: tagline, feature→benefit bullets, full story. Outputs `.md` + listing `.txt`. |
| 24 | `faq-builder` | FAQ Builder | $2.50 | Q&A pairs → categorized FAQ with table of contents. Outputs `.md` + `.json`. |
| 25 | `meeting-notes-structurer` | Meeting Notes Structurer | $2.00 | Raw notes → structured minutes: decisions, action items with owners (parsed from `DECISION:` / `ACTION: (owner)` markers). Outputs `.md` + `.json`. |
| 26 | `invoice-pack` | Invoice Pack | $3.00 | Line items → invoice/quote/receipt with computed subtotal, tax, total. Outputs `.txt` + styled `.html`. |
| 27 | `contract-lite-kit` | Contract Lite Kit | $4.00 | Parties + terms → plain-language service-agreement template (8 standard clauses + custom extras). Plainly marked as a draft, **not legal advice**. |
| 28 | `resume-kit` | Resume Kit | $5.00 | Experience input → formatted resume + tailored cover letter. Outputs `resume.md` + `cover-letter.md`. |
| 29 | `study-guide-builder` | Study Guide Builder | $3.00 | Outline → objectives, topics, key terms, self-quiz with separate answer key. Outputs `.md` + `.json`. |
| 30 | `caption-forge` | Caption Forge | $2.00 | Topic brief → 3 caption variants (classic/punchy/numbered) + tone-appropriate CTAs + hashtags **derived deterministically from the brief's own words** (never a copied bank). |
| 31 | `press-release-drafter` | Press Release Drafter | $4.00 | Fact sheet → formatted release: FOR IMMEDIATE RELEASE, headline, dateline, facts, quote, media contact, boilerplate. Outputs `.md` + `.txt`. |
| 32 | `lesson-plan-builder` | Lesson Plan Builder | $3.00 | Curriculum outline → lesson plan with objectives, timed activities, materials, assessment, differentiation, closure. Outputs `.md` + `.json`. |

## What it earns

Quoted amounts above are **pricing advice** ($2.00–$5.00 entry, per the
founder pricing doctrine: entry $1–5, ~30–60% below the giants). Realistic
sale shapes:

- One-off document kits (invoice-pack, contract-lite-kit, resume-kit,
  press-release-drafter, newsletter-drafter): sold per deliverable.
- Repeatable content ops (changelog-composer, caption-forge,
  meeting-notes-structurer): sold per run or monthly seat.

`run()` returns a `WorkReport` with `quoted_amount_usd` — a quote, not
revenue. Income is recorded **only** by Chauncey via
`engine.record_income(..., basis="confirmed")`. The engine never invents
income; the 70/30 split (keeper/pool) applies at record time, and all money
paths go through the Cybrus MoneyGateway.

## Honest limits

- These are **assembly engines**, not authors: output quality is bounded by
  input quality. Empty params produce an honest skeleton with placeholder
  markers, never hallucinated filler.
- The contract-lite-kit is a **plain-language template, not legal advice**
  — it says so in the artifact itself.
- Hashtags are derived from the user's own brief words; there is no
  trend-awareness and no claim of reach optimization.
- No network, no LLMs, no third-party code — everything is original
  stdlib Python in `core/levi/income/gen_content.py`.
- Tests: `tests/test_income_content.py` — 13 tests: registry presence,
  per-generator dry-run + real smoke, dry-run file safety, invoice math,
  notes-extraction correctness, JSON parse checks, quoted-price bounds,
  engine end-to-end, and a guard that `run()` never records income events.

## Files

- `core/levi/income/gen_content.py` — the 12 registered generators
- `tests/test_income_content.py` — the test suite
