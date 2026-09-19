# RESCUE & REMODEL — the forge's site-rescue service

**Keeper's identity (2026-09-17): the Site Lift IS Rescue & Remodel.**
One capability, two names: the lift is the rescue, the reveal is the
remodel. NeighborOS's hedged capability — the thing other platforms
don't want out — built un-hedged.

**Keeper's cut `ab1f8ac`** (LEXICON.md): *Bar Rescue meets Extreme Makeover:
Home Edition, directed at businesses and their websites/apps. The AI/SI
operators walk in, diagnose what's failing, then tear down and rebuild —
revision, upgrading, remodeling. Every business gets the rescue episode;
every site gets the reveal.*

**Status:** design + build, worker 8 (rescue architect).
Proving bar: green, lawful, **keeper-reviewed** — this doc and the build
are marked **ready-for-review**; the keeper's review is his to give.

**Hierarchy (binding):** Alpha & Omega first and last → Levi head of all
beneath them → the rest. Rescue & Remodel sits under Levi's head, beside
the other forge recreations.

**Home:** `core/levi/rescue/` · **Law:** revival laws — original LEVI-native
recreation, never a copy of any existing service. Nothing is ever deleted;
the stone records every rescue.

---

## 1. The service, in one breath

A business owner invites LEVI's operators into their website or app.
The operators walk it like a Bar Rescue host walks a failing bar —
cameras on, no staged problems — then rebuild it like an Extreme
Makeover crew: revision, upgrading, remodeling. The episode ends with
the reveal: a before/after receipt that shows *exactly* what changed,
verified, owner-approved. The whole episode is etched in the stone:
append-only, nothing deleted.

Five acts, each gated:

```
intake → audit → rescue plan → remodel → reveal
  │         │          │            │         │
consent  evidence   owner      rebuild     owner
invite   or it      approves   + verify    accepts
         doesn't    the plan   the fix     the reveal
         ship
```

Every consequential step rides the forge rail —
**Plan → Preview → Permission → Execute → Verify → Receipt**
(`core/levi/forge/rail.py` over `core/levi/policy/gates.py`).
The business owner is the approver at the two human gates: the rescue
plan and the reveal. Findings carry evidence or they don't ship.
The remodel changes nothing the owner hasn't seen in preview.

## 2. Act one — intake (consent-first)

We only walk into sites we're invited into. Full stop.

- `issue_invitation(home, owner=…, business=…, site_url=…, scope=[…])` —
  the operator records the invitation: who owns the business, which
  site/app, and the **scope bounds** (URL prefixes the walk may touch).
  Nothing fetches yet. Event: `intake.invited`.
- `accept_invitation(home, invitation_id, owner_note="")` — the owner
  accepts; consent is now on the record. Event: `intake.accepted`.
- `require_consent(home, invitation_id)` — every later act calls this
  first. Invited-but-not-accepted, unknown, or missing invitation →
  `ConsentRefusedError`. No walk-in without invitation.

The scope bounds are enforced by the walk: any URL outside the invited
prefixes is refused and the refusal is on the record.

## 3. Act two — the rescue audit (Bar Rescue)

The audit is a set of **checks**, each a small probe over a walked site:

```
WalkContext { url → { status, text, links, forms, sha256, fetched_at } }
   → check probe(walk) → Finding | None
```

The honesty laws (binding):

1. **A finding ships only with evidence.** `Finding.evidence` is a
   non-empty list of `{kind, ref, note}`. A probe that returns a
   finding with no evidence has that finding **dropped** into
   `dropped_hypotheses` — never into the report. No invented problems.
2. **Scores are deterministic.** `score = max(0, 100 − Σ severity
   weights)` with published weights (critical 25, high 15, medium 8,
   low 3). No model vibes, no invented sub-scores.
3. **The walk is receipted.** Every fetch rides the forge browser
   surface at LOW risk; refusals (out-of-scope, non-document) are
   on the record.

Standard check set (`DEFAULT_CHECKS`, all honest — they read only
what the walk actually saw):

| check | what it proves | evidence |
|---|---|---|
| `reachable` | homepage answers 200 | status code + fetch receipt |
| `has-title` | a real `<title>` exists | the title text or its absence |
| `has-heading` | page has a top-level heading | heading text or its absence |
| `contact-visible` | phone/email pattern on site | the matched strings |
| `links-resolve` | every link marker has a target | count + the dead markers |
| `forms-described` | forms carry named fields | field descriptors |

`run_audit()` returns an `AuditReport`: findings, the score,
`dropped_hypotheses`, walk receipts. Persisted to
`audits/<audit-id>.json`; event `audit.completed`.

## 4. Act three — the rescue plan (preview-first, operator-approved)

Each finding becomes a **rescue item**: the action, a human-readable
preview of what will change, risk level, reversibility, affected
surface. Each item is put through the rail as a proposal
(`rail.plan(...)`) so the owner sees exactly what the operator is
asking permission for.

- `build_plan(home, audit_report)` — draft plan; event `plan.drafted`.
- `preview_plan(home, plan_id)` — the owner-facing view: every item's
  preview + risk + reversibility.
- `approve_plan(home, plan_id, owner)` — the owner approves; every rail
  proposal is approved with the owner's note. Event `plan.approved`.
- `deny_plan(home, plan_id, owner, note)` — likewise; event
  `plan.denied`.

Risk mapping is honest, not padded: low→LOW, medium→MODERATE,
high/critical→HIGH. Remodel refuses to run on a plan that isn't
owner-approved (`PlanNotApprovedError`).

## 5. Act four — the remodel (Extreme Makeover)

`run_remodel(home, plan_id, *, surfaces, transforms)`:

1. Gate: plan must be `approved`.
2. Episode directory: `episodes/<episode-id>/{before,after,receipts}/`.
3. For each item, in order:
   - **Before**: snapshot the artifact (walked page or rebuild-workspace
     file) → sha256.
   - **Plan/Preview**: the change is described; the before/after diff
     preview is shown. HIGH-risk items wait on the owner's permit.
   - **Execute**: `transforms[item_id](before) → after` runs on the
     sandbox computer surface (writes preview-gated, deletes to trash —
     the computer's own laws), or the page is re-fetched on the browser
     surface.
   - **Verify**: the item's original audit check re-runs against the
     after-state. Resolved → `verified=True`. Not resolved → the
     result is receipted as failed, honestly — the stone records
     misses too.
   - **Receipt**: the rail receipts the whole step.
4. **Versioned changes**: the episode dir is committed via the code
   forge seam (`levi.forge.gitx`); if git is unavailable the episode
   keeps content-addressed before/after copies and says so.

Transforms are operator-supplied callables — the remodel engine
doesn't invent site fixes; it applies, verifies, and receipts them.
Event per item: `remodel.item_done` / `remodel.item_failed`.

## 6. Act five — the reveal (before/after receipt)

`build_reveal(home, plan_id, results)` assembles the reveal receipt:

- per item: `before_sha256`, `after_sha256`, `verified`,
  human `change_summary`, the diff stat;
- episode-level: score before → score after (re-audit of the
  after-state), all rail receipts linked.

**Completeness law:** every approved plan item must have a result with
both hashes, or `build_reveal` raises `IncompleteReceiptError` — a
reveal never ships half-built. `approve_reveal(home, reveal_id, owner)`
closes the episode; event `reveal.accepted`. Nothing is deleted;
the stone holds the whole episode.

## 7. The stone — nothing is ever deleted

`core/levi/rescue/ledger.py` keeps the **Rescue Stone**: one append-only
`stone.jsonl` per home. Every stage transition appends
`{ts, event, episode_id, detail}`. There is **no delete path** — the
module exposes no deletion API at all. `ledger()` reads oldest-first.

Seam (noted, not forced): the revival yard (`core/levi/revival/yard.py`)
holds the dynasty's stone ledger for raisings. A future cut can raise
each completed rescue episode in the yard as a raising of kind
`"rescue"`; the rescue ledger entry carries everything the yard needs
(episode id, business, before/after, receipts). Worker 4's module was
not touched for this.

## 8. The forge surfaces — adapt, don't rewrite

`core/levi/rescue/seams.py` is the adapter layer:

- **Browser** (`levi.forge.browser.open_browser`) — the walk surface.
  `walk_invitation()` opens the invited URL(s) inside scope, renders
  pages to the walk context. Lazy import; `SurfaceUnavailableError`
  if the surface isn't landed, honest and loud.
- **Computer** (`levi.forge.computer.open_machine`) — the rebuild
  surface. Transforms run inside the machine's deny-closed root.
- **Code forge** (`levi.forge.gitx.run_git`) — episode versioning.
- **NeighborOS gig dispatch** — the natural tie-in: a remodel is
  dispatched work. `dispatch_gig(home, plan_id)` drafts a gig-shaped
  record from the approved plan (title, category `site-rescue`,
  scope tokens, estimate band from item count × severity) and, if
  `levi.neighbor.post` is importable, hands it to `draft_gig` for the
  real NeighborOS pipeline (`preview_gig` → owner confirm →
  `publish_gig`). If neighbor isn't importable, the draft is returned
  portable with `dispatched=False` and the reason on the record.
  The seam is one function wide; nothing in rescue depends on neighbor
  internals. (Site Lift, the NeighborOS flagship under worker 7, is the
  natural dispatcher of these gigs.)

All three forge surfaces are **composed, not rewritten** — the rescue
modules call their public APIs through thin adapters. Where a surface
isn't landed yet, the adapter raises instead of faking.

## 9. Module map

```
core/levi/rescue/
  __init__.py   home resolution (LEVI_RESCUE_HOME → ~/.levi/rescue),
                stage constants, hierarchy banner
  intake.py     issue/accept invitation, require_consent, owner-stated
                cost line items (validate_costs)
  audit.py      checks, evidence law, honest scoring, run_audit
                (carries the analytics baseline)
  analytics.py  business analytics: measure() over the walk (10 published
                metrics, deterministic), Baseline, healthy targets,
                metric_deltas; cost pillar: cost_baseline,
                propose_cost_targets (LEVI-native equivalents, verified
                importable; hosting-rate "rehost" proposals — the
                keeper's word is that even hosting cost rates get
                attacked), cost_savings, hosting_savings (hosting broken
                out $/mo + $/yr)
  plan.py       build/preview/approve/deny plan, rail proposals;
                items carry numeric targets, plans carry cost targets
  remodel.py    run_remodel: before/after, verify, receipts, versioning
  reveal.py     build_reveal, completeness law, owner acceptance;
                metric before/after deltas; attest_costs + verified
                savings receipt (hosting savings shown separately
                $/mo + $/yr alongside the total)
  ledger.py     the Rescue Stone: append-only, no delete path
  seams.py      forge-surface adapters + NeighborOS gig-dispatch seam
```

Pipeline entry points (Python API):

```python
from levi.rescue import intake, audit, plan, remodel, reveal, seams

inv = intake.issue_invitation(
    home,
    owner="M. Torres",
    business="Torres Tacos",
    site_url="https://torrestacos.example",
    scope=["https://torrestacos.example/"],
)
intake.accept_invitation(home, inv.id, owner_note="walk it, fix it")

walk = seams.walk_invitation(home, inv.id)  # browser surface
report = audit.run_audit(home, inv.id, audit.DEFAULT_CHECKS, walk)
p = plan.build_plan(home, report)
plan.approve_plan(home, p.id, owner="M. Torres")  # owner gate
results = remodel.run_remodel(
    home, p.id, surfaces=seams.forge_surfaces(home), transforms={...}
)
rv = reveal.build_reveal(home, p.id, results)
reveal.approve_reveal(home, rv.id, owner="M. Torres")
```

## 10. Tests (hermetic)

`tests/test_rescue_*.py`, LEVI_RESCUE_HOME pinned to tmp, no network —
the browser surface is faked behind the seam:

- `test_rescue_consent.py` — no walk-in without invitation: unknown
  id, invited-but-not-accepted, and out-of-scope URL all refuse;
  accepted invitation walks.
- `test_rescue_audit.py` — audit honesty: a probe returning an
  evidence-free finding is dropped into `dropped_hypotheses`, never
  into findings; every shipped finding carries non-empty evidence;
  scoring is deterministic.
- `test_rescue_gates.py` — the plan-approval gate: remodel on a
  draft/denied plan raises `PlanNotApprovedError`; only approved
  plans remodel.
- `test_rescue_reveal.py` — reveal completeness: a result missing
  `after_sha256` (or any approved item without a result) raises
  `IncompleteReceiptError`; a complete reveal verifies and closes.
- `test_rescue_ledger.py` — the stone: every stage appends; reads
  oldest-first; no deletion API exists on the module.

## 11. Honest gaps (for the keeper's review)

- The audit's `DEFAULT_CHECKS` read the forge browser's *served-HTML*
  rendering — JS-rendered apps are audited as their served HTML, and
  the walk receipt says so (the browser surface's honest limit).
- Analytics measures the site's own served content only: no visitor
  tracking, no third-party beacons, no surveillance of anyone. Weight
  metrics are performance proxies, not timings — the rail never
  claims a measured load time it didn't measure.
- Money is owner-stated, always labeled: the cost baseline totals the
  owner's declared spend; the savings receipt verifies the arithmetic
  on figures the owner put on the record. The rail meters nothing.
- Cost-target proposals are drafts the owner approves — a LEVI-native
  replacement is only proposed when the module verifiably imports;
  fit-check before canceling any subscription stays the owner's call.
- Hosting is attacked as a first-class line: the recovered Hybrid
  Cost-Cutting Combos research (old-school technique + modern software,
  2026-09-17) wires five drafted combo classes into the proposals —
  static-first rebuild, de-containerize, schedule-don't-idle,
  downsize-the-iron, de-manage-the-database. Each names its combo and
  old/new mix, fires only on hosting lines after the LEVI_EQUIVALENTS
  honest-import check (a verifiable in-repo module outranks the
  pattern), and carries no invented savings numbers — the report's
  figures are web-index estimates, not live-verified. The generic
  "rehost" plays (right-size, shop cheaper, consolidate bills) stay
  the fallback. The owner fit-checks, picks, and sets the target on
  approval; the rail never invents a hosting rate. The reveal shows
  hosting savings ($/mo, $/yr) separately alongside the total; no
  hosting on the record means the receipt says so, not zero dressed
  up as a win.
- Transforms are operator-supplied: the remodel *applies and verifies*
  fixes; it does not author site redesigns on its own. A future cut
  can grow a transform library (accessibility, performance, SEO packs).
- The NeighborOS dispatch is a seam, not a live wire: gig drafts are
  portable records until neighbor's posting pipeline is the caller.
- Keeper review pending — nothing here claims it.
