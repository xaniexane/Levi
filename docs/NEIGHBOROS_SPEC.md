# NeighborOS — LEVI Addition Spec

**Status:** Phase 1 partially built (status updated 2026-09-18) — Customer app (`post.py`: job intake, Job DNA, estimate bands), Worker app (`work.py`: registry, Credential Graph claims, claim flow, availability, proof-of-work stream, disputes), NeighborPay settlement ledger (`pay.py`: plan → settle → receipt; real rails stay labeled external references), and fee math (`monetize.py`: corpus bands, 90% worker-keep floor) are live in `core/levi/neighbor/`, with `store.py` (JSONL stores), `policies.py` (operator config), `cli.py` (`levi neighbor`, cell-scoped), `lift.py` (the Site Lift), and tests (`tests/test_neighbor_core.py`, `test_neighbor_lift.py`, `test_neighboros.py`). Still spec-only: `waitlist.py` (recruiting), `admin.py` (Admin Command Center), `twins.py` (property twins), `supply.py` (supplier portal), `academy.py` (Academy & Credential Network), Business Contractor crews (no team code in `work.py`), ROI Upgrade Engine, Launch Readiness Score, PWA shell, push notifications, external payment rail plug-ins, white-label. Per-item marks in §4 and §13 below.
**Date:** 2026-09-16 (spec); build status updated 2026-09-18
**Canon:** PROJECT IDENTITY: Levi AI (2026-07-27) — *"NeighborOS = gig dispatch"*

## 1. Canon grounding

NeighborOS is not a new idea and not a rival to LEVI. In Chauncey's own
master DNA snapshot (July 27, 2026), the masthead reads:

> **PROJECT IDENTITY: Levi AI (Levi); Omega = main Android app;
> NeighborOS = gig dispatch; DemandPulse = economic intelligence/advisor.**

NeighborOS is the **gig-dispatch organ** of the organism, sitting in the
ECONOMIC ENGINE layer (NeighborOS + DemandPulse feed) of the system DNA tree.

What the corpus defines (Gemini chats, 2026-07-27):

- **Gig-dispatch PWA**: neighborhood gig marketplace — customers post jobs,
  workers accept them, dispatch matches the two.
- **NeighborPay**: the payments side. Core law: **workers keep 90%+**;
  the platform earns **only on completed + paid jobs**.
- **Property Twin moat**: Worker/Property Digital Twins — a living record
  of a property (systems, health score, predictive maintenance).
- Moats: **Job DNA, Proof-of-Work Ledger, Credential Graph, Neighborhood
  Liquidity Engine**, ROI Upgrade Engine, Launch Readiness Score.
- 10 required systems in priority order: public website + recruiting;
  Admin Command Center; Customer app; Worker app; Business Contractor app;
  Property Manager app; Supplier portal; Academy & Credential Network;
  NeighborPay payments; Monetization Engine.
- Market activation: **Waitlist Only → Recruiting → Soft Launch →
  Active Dispatch**, with compliance gates between stages.
- Zero-founder-startup-cost model: manual dispatch/verification first,
  lead CRM, earn-first fees/commissions.
- Monetization bands (corpus): standard commission 8–12%, emergency
  12–18%; AI estimate/design fee $5–50; tiers Free Worker / Pro Worker
  $19–39/mo / Business $79–199/mo / Home+ $14.99/mo / Property Manager
  $99–499/mo; dynamic commission by job size; no single revenue stream
  >30–40% of total.

This spec translates all of that into a **LEVI-native addition**: local-first,
stdlib-only, free core forever — an addition, never a rebuild of TaskRabbit,
Angi, or Thumbtack.

## 2. One-line definition

**NeighborOS is LEVI's gig-dispatch organ: neighbors post work, trusted
workers claim it, every job is fingerprinted (Job DNA), proven
(Proof-of-Work Ledger), and settled (NeighborPay ledger) — all on local
infrastructure the operator owns.**

## 3. Non-negotiable laws (LEVI-native restatement of the corpus 10)

1. **Zero-startup-cost.** The core runs on hardware already owned. No paid
   APIs, no per-seat SaaS, no tolls — the hard-route law.
2. **Free core forever.** Posting, claiming, dispatching, twins, and the
   ledger are free. Money is made in the layers above (see §11).
3. **Earn-first monetization.** Nothing is charged before value is delivered.
   Platform fees exist only on completed + paid jobs.
4. **Workers keep 90%+. ** A floor, not a target: `worker_keep_floor = 0.90`
   in policy config. This is the fairtrade law made numeric
   (symmetric-by-construction).
5. **Compliance-gated expansion.** Waitlist → Recruiting → Soft Launch →
   Active Dispatch. Each gate is a checklist in config, not vibes.
6. **Twin-powered moat.** Every property and worker accumulates a twin;
   twins are the retention engine. Data stays local to the operator.
7. **Dispatch-first.** Matching work to workers is the core loop; everything
   else (academy, suppliers, analytics) serves it.
8. **Local-first, PWA-later.** The core is CLI + local data. A mobile PWA is
   a later addition, not the foundation.
9. **Operator-configurable.** Fees, gates, categories, and policies are
   config, never code forks.
10. **Full audit logging.** Every dispatch decision, payout, and override is
    append-only logged. Blueprints 2–10 sit behind feature flags.

## 4. The 10 systems → LEVI modules (priority order)

| # | Corpus system | LEVI module (`core/levi/neighbor/`) | Built? |
|---|---------------|--------------------------------------|--------|
| 1 | Public website + recruiting | `waitlist.py` — local waitlist/CRM (JSONL), invite codes | ❌ spec-only — module absent |
| 2 | Admin Command Center | `admin.py` — `levi neighbor admin` CLI: gates, policies, disputes | ❌ spec-only — module absent (gates/policies live in `policies.py` + `cli.py`) |
| 3 | Customer app | `post.py` — `levi neighbor post` — job intake, estimate bands, Job DNA, draft→preview→publish | ✅ built |
| 4 | Worker app | `work.py` — `levi neighbor work` — browse/claim, availability, proof-of-work stream, disputes | ✅ built |
| 5 | Business Contractor app | teams inside `work.py` (multi-worker crews), phase 2 | ❌ spec-only — no crew/team code in `work.py` |
| 6 | Property Manager app | `twins.py` — property twins, portfolios, health rollups | ❌ spec-only — module absent (portable worker passport lives in `lift.py`) |
| 7 | Supplier portal | `supply.py` — materials/equipment referrals ledger, phase 2 | ❌ spec-only — module absent |
| 8 | Academy & Credential Network | `academy.py` — credentials feed the Credential Graph | ❌ spec-only — module absent (credential *claims* with provenance exist in `work.py`) |
| 9 | NeighborPay payments | `pay.py` — **local settlement ledger** (see §8) | ✅ built |
| 10 | Monetization Engine | `monetize.py` — fee computation, tiers, reports | ✅ fee math built (`compute_fee`, 90% floor); ⚠️ tiers/reports not present |

Phase 1 builds systems 1–4 + 9 (ledger) + 10 (fee math). The rest sit behind
feature flags, per the corpus blueprint order.

## 5. Moats, LEVI-native

- **Job DNA.** Every job gets a stable fingerprint (category, scope tokens,
  location cell, price band, photo hashes). DNA powers matching ("workers who
  did jobs with this DNA"), estimate calibration, and fraud detection
  (same-DNA reposts). Pure local computation.
- **Proof-of-Work Ledger.** Append-only JSONL: check-in, progress photos,
  check-out, customer sign-off. A job is not *done* until the ledger says so;
  a payout is not *released* until the ledger + sign-off agree. This is the
  Verify + Receipt half of the safety pipeline.
- **Credential Graph.** Worker credentials (academy completions, licenses the
  worker asserts, customer endorsements) as a local graph. Credentials are
  *claims with provenance*, never verified-by-us unless the operator runs a
  check — honest labeling throughout.
- **Neighborhood Liquidity Engine.** Per-neighborhood supply/demand tracking:
  open jobs vs. active workers by category. Cold neighborhoods get recruiting
  nudges; hot ones get priority-dispatch pricing. All computed locally from
  the ledger.
- **Property Twin + Health Score.** Per property: systems inventory
  (roof, HVAC, plumbing, electrical…), condition scores, maintenance log,
  predictive reminders ("water heater is 11 years old — budget $1,200").
  The twin is the moat: leaving the platform means abandoning the twin.
- **ROI Upgrade Engine** (phase 2): twin-driven suggestions
  ("insulation upgrade pays back in 3.2 winters at local rates").
- **Launch Readiness Score** (phase 2): per-neighborhood 0–100 from waitlist
  depth, worker supply, and gate checklists.

## 6. Data model (stdlib, local-first)

All under `~/.levi/neighbor/`:

- `gigs.jsonl` — id, title, category, description, photo refs, estimate,
  neighborhood cell, requester, status
  (`open → offered → accepted → in_progress → done → paid`, plus `disputed`),
  job DNA, ledger refs.
- `workers.jsonl` — id, profile, credential refs, rating, availability,
  home neighborhood.
- `twins/property_<id>.json` — systems inventory, health scores,
  maintenance log, reminders.
- `ledger.jsonl` — proof-of-work entries: gig_id, worker, check-in/out,
  photo refs, sign-off, payout refs.
- `settlements.jsonl` — NeighborPay ledger: what is owed, to whom, status.
- `policies.json` — commission bands, `worker_keep_floor`, gate checklists,
  categories. Config, not code.

No database server. No network calls in the core loop.

## 7. Dispatch flow (safety pipeline)

Every consequential step follows **Plan → Preview → Permission → Execute →
Verify → Receipt**:

1. **Post** — customer describes the job; optional photos. LEVI drafts the
   Job DNA and an estimate band (from same-DNA history, honestly labeled
   when history is thin).
2. **Preview** — requester sees the DNA, estimate band, and candidate
   workers (Credential Graph + proximity + availability) before publishing.
3. **Match** — workers get notified (local daemon queue first; push later).
   Accept/decline with one action.
4. **Execute** — check-in opens the proof-of-work stream.
5. **Verify** — check-out + photos + customer sign-off close the ledger.
6. **Receipt** — settlement entry written; fee computed per policy;
   worker keeps ≥90%. Both sides get a receipt.

Disputes freeze settlement and route to the Admin Command Center queue —
human decision, never autonomous.

## 8. NeighborPay: ledger in core, rails as plug-ins

This is the critical honesty boundary:

- **In the free core**, NeighborPay is a **settlement ledger**: who owes whom,
  how much, for which proven job, under which fee policy. It never touches
  real money and never claims to.
- **Real money movement** (Stripe, bank transfer, cash logging) lives in
  **labeled external plug-ins** — references, never core. The core records
  *that* a settlement was paid through rail X (with a reference), not the
  payment itself.
- The corpus "background check pass-through + small admin fee" becomes:
  checks are external services the operator chooses; LEVI records the claim
  and its provenance, nothing more.

## 9. Roles (7, from corpus)

Customer, Worker, Business Contractor (crews), Property Manager, Supplier,
Academy instructor/student, Admin. Roles are lenses for the CLI views, not
identity or security boundaries — same rule as personas.

## 10. Activation gates

`levi neighbor admin gates` enforces, in order:

1. **Waitlist Only** — landing + invite codes, no dispatch.
2. **Recruiting** — worker onboarding, credential seeding, no customer jobs.
3. **Soft Launch** — one neighborhood cell, manual dispatch assist, capped
   job volume.
4. **Active Dispatch** — full matching, all categories the operator enables.

Each gate is a checklist in `policies.json`. Skipping a gate requires an
explicit operator override, logged.

## 11. Monetization (free core; paid layers)

Free core forever: posting, claiming, dispatch, twins, ledger, receipts.

Paid layers (the LEVI economics — free to produce, charge for the layers):

- **Managed neighborhood hosting** — LEVI runs the dispatch op for a
  neighborhood/HOA/property manager: $99–499/mo (corpus band).
- **Curated demand feed** — DemandPulse scores which job categories are
  heating up per neighborhood; workers/operators subscribe to the feed.
- **Premium packs** — estimate calibration packs, twin template packs
  (per property type), academy course packs.
- **Platform fee on completed + paid jobs** — only where the operator runs
  the marketplace: standard 8–12%, emergency 12–18%, dynamic by job size
  (<$100: 12%; $100–500: 10%; $500–2,000: 8%; >$2,000: 6%), worker keeps
  ≥90% always. No fee on unfinished or unpaid jobs — ever.
- **Pro Worker** $19–39/mo: reduced commission, unlimited AI estimates,
  auto-bidding, analytics. **Home+** $14.99/mo: twin hosting, seasonal
  reminders, discounted consults.

Long-term guardrail (corpus): no single revenue stream >30–40% of total.

## 12. Fairtrade alignment

NeighborOS is the fairtrade doctrine with numbers attached:

- *Open-gate generosity*: the core that earns trust (dispatch, twins,
  ledger) is free; the platform only eats when the worker gets paid.
- *Symmetric-by-construction*: the 90% worker floor is in config, visible
  to everyone, not a marketing claim.
- *One-door exit*: twins and ledger export in one command. Leaving costs
  nothing; the twin is what makes staying worthwhile — honest retention,
  never lock-in.
- *Earned continuity*: subscriptions buy convenience (hosting, feeds,
  packs), never access to work itself.

## 13. Build phases

- **Phase 1 — Foundation Launch MVP**: systems 1–4, 9 (ledger), 10 (fee
  math); one neighborhood cell; JSONL stores; CLI only.
  - ✅ systems 3 (Customer app → `post.py`), 4 (Worker app → `work.py`),
    9 (ledger → `pay.py`), 10 (fee math → `monetize.py`); JSONL stores
    (`store.py`, append-only); cell-scoped CLI (`cli.py` `--cell`,
    `springfield-test` in the soft-launch gates).
  - ❌ system 1 (recruiting/waitlist — no `waitlist.py`), system 2
    (Admin Command Center — no `admin.py`).
- **Phase 2** (flags — all spec-only): ❌ crews, ❌ supplier portal
  (`supply.py`), ❌ academy wiring (`academy.py`), ❌ ROI engine,
  ❌ readiness scores.
- **Phase 3** (flags — all spec-only): ❌ PWA shell, ❌ push notifications,
  ❌ external payment rail plug-ins (rails stay labeled external references
  in `pay.py`), ❌ white-label.

## 14. What it is not

- Not a rebuild of TaskRabbit/Angi/Thumbtack — the addition is the
  twin-powered, ledger-proven, worker-keeps-90% model they refuse.
- Not a payment processor, not a background-check vendor, not an insurer.
  Those are external references; the core keeps the ledger and the proof.
- No dark patterns: no fake urgency, no hidden fees, no worker
  misclassification games. The fee math is inspectable by both sides.

## 15. Acceptance criteria

- Post → match → proof → settlement → receipt completes locally with zero
  network calls; full suite green including new `tests/test_neighbor*.py`.
- Worker keeps ≥90% on every settlement in the test fixtures; fee math
  matches the corpus bands.
- A disputed job freezes settlement and appears in the admin queue; no
  autonomous payout.
- One-command export of a worker's twin + ledger history.
- Gate checklists enforced: dispatch commands refuse outside Active
  Dispatch (or Soft Launch caps) without a logged override.

## 16. Open questions for Chauncey

1. PWA: rebuild the corpus single-file React app LEVI-native later, or keep
   CLI-first indefinitely?
2. Real-money rails: which plug-in first when the time comes (Stripe is the
   obvious reference), or cash/manual-only at launch?
3. First neighborhood cell: Springfield test cell, or elsewhere?
