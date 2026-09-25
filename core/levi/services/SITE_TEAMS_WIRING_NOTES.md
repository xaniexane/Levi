# Site Lift Tailored Teams — wiring notes + docs

Chauncey's canon: "Site Lift must ship with TAILORED TEAMS for businesses
+ other specialized packs (not just the lift report — the crew that fills
the gaps it finds)" and "tailored team = Site Lift analysis + installed
crew as one offer."

## What shipped

Two new modules in `core/levi/services/`, stdlib-only:

- **`site_teams.py`** — data-driven team packs. 5 packs: `restaurant`,
  `salon`, `shop`, `trades`, `generic`. Each pack has roles (greeter,
  booker, faq-answerer, review-responder; shop swaps booker for
  order-tracker). Each role declares:
  - `covers`: lift measured check ids it fills (e.g. booker covers
    `t-booking`; faq-answerer covers `t-faq`, `t-pricing`;
    review-responder covers `t-proof`; greeter covers `f-contact`,
    `f-cta`)
  - `checklist`: per-role install tasks
  - `escalation`: handoff rules (what the crew member must NOT decide
    alone — always escalates to the human owner with context)
  - No business names hardcoded; packs are keyed by business TYPE.
  - `validate_packs()` runs at import: every covered check id must
    exist in the lift's measured checks, every role needs a non-empty
    checklist and escalation rule.

- **`site_team_match.py`** — matching + offer assembly.
  - `failed_findings(report)`: every failed MEASURED check, crown
    `c-reg:` prefixes normalized to the base id (deduped), attested
    checks (`s-*`, `c-goal-*`, `c-showcase`) excluded — crew answers
    measured gaps, not attestations.
  - `recommend_pack(report)`: pack covering the most failed findings;
    ties break in PACK_ORDER (most specific first, generic last) —
    deterministic.
  - `match_report(report, pack_id=None)`: role-level coverage per
    finding; anything no role covers lands in `unmatched` and is
    printed as "no crew covers this". NEVER silently dropped.
  - `assemble_offer(...)`: one offer object —
    `offer_id = team_<pack>_<report_hash[:8]>` (deterministic),
    `report_hash` (sha256 of canonical report JSON), per-role install
    checklist + findings covered, unmatched findings with the honest
    note, and a paper quote via the founder price advisor
    (`quote_pack`: tier=entry, optional giant-price anchor, never at or
    above the giant). Quote, not a charge — payment rides Cybrus only.

## CLI

Wired directly (services/cli.py + core/levi/cli/main.py were clean in
git status — no patch spec needed):

- `levi service lift <site-dir> --with-team [--pack P] [--no-quote]
  [--giant-price USD] [--strategy volume|margin]` — run the lift, then
  match + print the crew and save the offer.
- `levi service teams <report-id> [--pack P] [--no-quote]
  [--giant-price USD] [--strategy volume|margin]` — match a saved lift
  report to a pack, print the crew, save the offer.

Offers persist under `$LEVI_HOME/services/team_offers/<offer-id>.json`.

## Coverage map (which gaps get crew, which don't)

| Finding (check id)      | Crew (role)        |
|-------------------------|--------------------|
| f-contact, f-cta        | greeter / booker   |
| t-booking               | booker / order-tracker (shop) |
| t-faq, t-pricing        | faq-answerer       |
| t-proof                 | review-responder   |
| f-title, f-meta-desc, f-viewport, f-h1, f-alt, f-pages, t-gallery, t-social, t-og, t-analytics, c-goal-* | NO CREW — site-build work or owner decisions; reported as unmatched |

## Honest limits

- The matching is deterministic, not intelligent: it keys on check ids,
  not on what the site actually does. A restaurant site with a booking
  gap and a salon site with a booking gap both get "the booker" — the
  crew role is a seat; the owner's specifics (hours, policies, tools)
  are filled in at install time from the per-role checklist.
- `recommend_pack` cannot know the business type from the report alone;
  when several packs cover the same gaps it picks the most specific
  pack by PACK_ORDER. The `--pack` override exists for when the keeper
  knows better than the heuristic — prefer the override when you know
  the business type.
- Unmatched findings (SEO/meta, gallery, social, analytics, viewport,
  page depth) are real gaps the installed crew does NOT fix — they are
  site-build work. The offer says so explicitly.
- Attested pass results (signature grafts, absorb-return notes,
  showcase summary) never drive matching; only measured checks do.
- Quotes are paper only: the price advisor advises, nothing moves, and
  this module invents no checkout. Money moves through the Cybrus
  gateway only.
- Crew roles are defined seats with checklists and escalation rules —
  actual agent wiring (which operator sits in which seat) is downstream
  work; this module ships the pack definition and the offer, not the
  running crew.
