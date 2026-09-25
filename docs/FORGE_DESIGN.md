# FORGE_DESIGN — the dynasty's Forge program

**Status:** design doc, living. **Keeper's cut 50e2979** ("the Site Lift")
made the NeighborOS seat ACTIVE — it is now the flagship recreation,
in-flight under worker 7.

## 1. What the Forge is

Canon (`docs/LEXICON.md`, entry cut as `f011bb0`): *the keeper widens the
forge — LEVI-native recreations of everything the operators need (code
forge, data stores, cloud services, workflow engines, the browser, the
computer itself), pure recreations in ways no one attempts or dares. Plus
the revival yard (things begun and left to die get raised again), the
multidomain social platform, agentic teams, the content creation machine,
and everything else to come.*

The Forge is the dynasty's **creation surface**: not one product but the
program that produces LEVI-native recreations of the operators' whole
stack. Hierarchy is binding: **Alpha & Omega first and last → Levi head
of all beneath them → the rest.** Every recreation sits under that head.

## 2. The recreation laws (binding)

1. **Original recreations with LEVI's twist** — never copies, never masks,
   never reverse-engineered. Study the idea, recreate it LEVI-native.
   The registry names the *idea* recreated (e.g. "code collaboration",
   "gig dispatch"), never a product as identity.
2. **The proving bar** — ship only when **green** (tests pass), **lawful**
   (canon laws honored), **keeper-reviewed** (the builder marks
   ready-for-review; nobody claims the keeper's review for him).
3. **Local-first, stdlib-only** — every recreation runs on the operator's
   own hardware with the standard library; nothing phones home.
4. **Ownership guarantee** — what the forge makes never leaves the
   operator's machine except by the operator's explicit push. Portable
   formats (git bundle, JSONL) so reputation and work travel with the
   operator, never held hostage.

## 3. Architecture: the registry is the program

The program stages **registry first, then recreations**:

```
                        ┌─────────────────────────┐
                        │  KEEPER (Chauncey)      │  declares, reviews
                        └────────────┬────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │  core/levi/forge/registry.py    │  the manifest ledger
                    │  (re-runnable, import-time      │  one manifest per
                    │   validated against live        │  recreation:
                    │   modules)                      │  name · idea · twist ·
                    └────────────────┬────────────────┘  module · ring · status
                                     │
        ┌────────┬────────┬──────────┼──────────┬────────┬────────┐
        ▼        ▼        ▼          ▼          ▼        ▼        ▼
     forge-   forge-   forge-    forge-     forge-   forge-  forge-
     code     data-    com-      brow-      revi-    so-     con-
     store    puter     ser       val      cial     tent   neighboros
      (w1)     (w2)     (w3)      (w3)      (w4)     (w5)    (w6)   (w7)
     green   planned  planned   planned   planned  planned planned in-flight
```

Each recreation is **one manifest**: `name`, the *idea* it recreates,
LEVI's native `twist`, `module` path, `ring` placement (open / closed /
government), proving-bar `status`
(`planned → in-flight → ready-for-review → green → keeper-reviewed`;
`reserved` is a recorded-only seat, not a stage).

The registry re-runs: `load_registry()` re-validates every module path
against live imports and re-discovers self-declared seats. Two pickup
mechanisms for later workers:

1. **Static seats** — the ledger lists sibling tracks' expected module
   paths; the moment a worker lands the file, the seat's `import_ok`
   flips True on the next load (seen live: worker 2's
   `levi.forge.datastore` and worker 4's `levi.revival.yard` both flipped
   during this build).
2. **Self-declaration** — any module may declare a top-level
   `FORGE_MANIFEST` dict; `discover_manifests()` walks the dynasty roots
   (`levi.forge`, `levi.revival`, `levi.lwp`, `levi.neighbor`) and seats
   it. Discovered manifests override static seats on name clash.

## 4. Worker seating (the six-plus-one)

| Seat | Idea recreated | Worker | Home | Ring | Status |
|---|---|---|---|---|---|
| `forge-code` | code collaboration | worker-1 | `core/levi/forge/` | open | **green** |
| `forge-datastore` | data stores | worker-2 | `core/levi/forge/datastore.py` | open | planned |
| `forge-flow` | workflow engines | worker-2 | automation-flow extension (declares itself) | open | planned |
| `forge-computer` | the computer itself | worker-3 | sandbox computer (declares itself) | open | planned |
| `forge-browser` | the browser | worker-3 | browser surface (declares itself) | open | planned |
| `forge-revival` | the revival yard | worker-4 | `core/levi/revival/yard.py` | closed | planned |
| `forge-social` | multidomain social platform | worker-5 | design docs only | open | planned |
| `forge-content` | the content creation machine | worker-6 | `core/levi/lwp/` | open | planned |
| **`forge-neighboros`** | **gig dispatch** | **worker-7** | **`core/levi/neighbor/`** | open | **in-flight** |

Ring rationale: `forge-code`, `forge-neighboros`, `forge-social` and the
infrastructure tracks sit **open** — the creational ring, where outside
minds run free with integrations (the code forge's export format is stock
git + open JSONL; NeighborOS's dispatch surface is a neighborhood
commons). `forge-revival` sits **closed** — resurrection is keeper-gated;
the diehard developers and the keeper decide what rises. `forge-teams`
sits **closed** — the team's charter lives with the keeper. No
**government** seats yet; the sandbox computer and NeighborOS earn
hardened editions there when the program reaches that stage.

## 5. The Site Lift — flagship recreation (ACTIVE)

Keeper's cut `50e2979`: the NeighborOS site-lift seat moved from RESERVED
to ACTIVE. Worker 7 builds it in `core/levi/neighbor/` per
`docs/NEIGHBOROS_SPEC.md` (2026-09-16). This worker does **not** build
NeighborOS; worker 7 owns that home. The registry's seat records it.

What the spec defines (the twist, LEVI-native):

- **The idea:** gig dispatch — neighbors post work, trusted workers claim
  it; every job fingerprinted (Job DNA), proven (Proof-of-Work Ledger),
  settled (NeighborPay ledger), all on local infrastructure the operator
  owns.
- **The un-hedging:** worker-owned portable reputation, transparent
  dispatch, direct worker-customer relationships, **workers keep 90%+**
  (`worker_keep_floor = 0.90` in config — the fairtrade law made numeric,
  symmetric-by-construction).
- **The laws:** zero-startup-cost; free core forever; earn-first
  monetization (platform earns only on completed + paid jobs);
  compliance-gated expansion (Waitlist → Recruiting → Soft Launch →
  Active Dispatch); twin-powered moat (property/worker digital twins);
  local-first, PWA-later; full audit logging; every consequential step
  follows Plan → Preview → Permission → Execute → Verify → Receipt.
- **The honesty boundary:** NeighborPay is a *settlement ledger* in the
  free core — it never touches real money. Real rails (Stripe, bank,
  cash) are labeled external plug-ins, never core.
- **What it is not:** not a rebuild of TaskRabbit/Angi/Thumbtack — the
  addition is the twin-powered, ledger-proven, worker-keeps-90% model
  they refuse. Not a payment processor, not a background-check vendor,
  not an insurer.
- **Phase 1:** `waitlist.py`, `admin.py`, `post.py`, `work.py` +
  `pay.py` (ledger) + `monetize.py` (fee math); CLI only; one
  neighborhood cell; JSONL stores under `~/.levi/neighbor/`. Twins,
  supply, academy, ROI engine, PWA sit behind flags.
- **Acceptance:** post → match → proof → settlement → receipt completes
  with zero network calls; 90%+ floor holds on every fixture settlement;
  disputes freeze settlement into the admin queue; one-command
  twin+ledger export; gate checklists enforced.

## 6. The revival-yard interface

Worker 4 owns the yard (`core/levi/revival/yard.py`); the forge holds the
seat and the interface. The contract between them:

```
raise (yard) → re-home (forge) → rebuild (forge, LEVI-native)
```

1. **Raise** — the yard identifies dead software (begun and left to die)
   and raises a revival candidate under the revival laws.
2. **Re-home** — the candidate is seated in the forge as a recreation
   (a new manifest or an adopted module), with provenance recorded.
3. **Rebuild** — the forge rebuilds it LEVI-native: stdlib-only,
   local-first, proving bar enforced. Nothing is resurrected as a copy.

The yard never writes directly into another recreation's home; it hands
the forge a candidate, and the forge seats it. Ring closed on the yard
side; the recreation it produces is ringed on its own merits.

## 7. Sequenced backlog — the ordered list of next recreations

The Site Lift is the flagship and builds **first** (in-flight). Behind
it, in order:

1. **`forge-neighboros`** — the Site Lift. Gig dispatch, in-flight
   (worker 7). Flagship: first recreation to carry the dynasty's
   fairtrade economics into the world.
2. **`forge-datastore`** — data stores (worker 2). The forge's ownership
   guarantee applied to data: plain-file portable stores, no hosted
   database dependency. Landed 2026-09-17; seat flipped live.
3. **`forge-flow`** — workflow engines (worker 2's automation-flow
   extension). Flows as plain local artifacts — rerunnable,
   inspectable, no cloud runner.
4. **`forge-computer`** — the sandbox computer (worker 3). The
   operator's own machine, recreated as a contained, auditable
   execution surface.
5. **`forge-browser`** — the browser surface (worker 3). The web as a
   recreatable tool of the forge, not a borrowed foreign application.
6. **`forge-revival`** — the revival yard (worker 4). Raise → re-home →
   rebuild per §6. Yard landed 2026-09-17; seat flipped live.
7. **`forge-social`** — the social platform (worker 5: design docs now,
   build later). Town square by forum by code commons — the forge's code
   home extended into the commons where operators gather.
8. **`forge-content`** — the content creation machine (worker 6, under
   `core/levi/lwp/`). L.W.P.'s writing physics as composable machinery:
   direction/phase/power, modes and forms — not templates.
9. **`forge-cloud`** — cloud-services surfaces. LEVI-native service
   surfaces with the forge's ownership guarantee: local-first,
   portable, no hostage formats. (An older `core/levi/cloud/` exists —
   the recreation is original LEVI-native work, never a copy of it.)
10. **`forge-teams`** — agentic teams. Teams of LEVI agents as forge
    citizens — work happens in the forge's own home, under the proving
    bar, with receipts. The six-plus-one forge workers are the first
    team; the recreation generalizes the pattern.
11. **Everything else to come** — new seats are cut by the keeper; the
    registry's `reserved` status exists for recorded-only seats the
    keeper has named but not yet activated.

## 8. Proving-bar mechanics

- `planned` — seat cut, owner named, nothing built yet.
- `in-flight` — the owner is building (NeighborOS now).
- `ready-for-review` — the builder marks it ready. This is the only
  claim a builder may make; it is a request, not a verdict.
- `green` — tests pass, stdlib-only, no stubs, lawful. The forge-code
  seat is green (`tests/test_forge.py`: 23 passed).
- `keeper-reviewed` — the keeper has reviewed and accepted it. Only
  then does a recreation ship. Never claimed by anyone but the keeper.

`refresh()` / `load_registry()` may be re-run any time; `proving_summary()`
reports status and ring counts for the keeper's dashboard.

## 9. Honest gaps (2026-09-17)

- `forge-flow`, `forge-computer`, `forge-browser`, `forge-social`,
  `forge-content`, `forge-cloud`, `forge-teams` have no modules yet —
  their seats are `planned` and honestly record it.
- The forge-code seat is green but **not keeper-reviewed**; nothing has
  shipped.
- No government-ring seats exist yet; hardened editions are future work.
- The registry's discovery walk imports candidate modules with guards;
  a module that raises at import is skipped, not seated — silent skips
  are logged nowhere yet (future: a discovery report).
