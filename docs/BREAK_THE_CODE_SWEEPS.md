# BREAK_THE_CODE_SWEEPS.md — the paid code-cracking challenge

**Status: design document.** No payment infrastructure, no live challenge
server, no real money handling, and no checker service are built here.
This doc is the spec for a future live system. Everything below is the
keeper's design; nothing here executes yet.

## The concept

Players pay **$2–5 to enter** a sweep and attempt to **crack parts of
Levi's and the others' code** — staged cryptic codings of increasing
complexity. Solo or collaborative: enter alone or as a team, if wanted.
Each stage is a piece of real LEVI code, rewritten as a cryptic coding
challenge. Crack it, prove it, unlock what's behind it.

This is the plain-sight layer as a sport: the codings look simple and
transparent — that *is* the cover. They see everything and recognize
nothing, until they earn the recognition.

## The pool: what enters a sweep

- The keeper decides what enters the sweep pool, stage by stage. Only he
  adds stages; he can pull any stage at any time.
- **Crown jewels never enter the pool.** SI core, vault crypto, signing
  and grant keys, the legion's control plane, keeper personal material —
  these are never staged, never hinted, never excerpted. The pool is
  real code, but never the bloodline.
- Stages are ordered by increasing complexity: early stages teach the
  shape of the codings; later stages are genuinely hard. The difficulty
  curve is the product — a $2 entry should feel fair, a final stage
  should feel legendary.

## What "crack" means: verifiable solve criteria

Every stage ships with a **checker** — a deterministic verifier, not a
judge's opinion. A crack counts if and only if the checker passes.
Typical stage shapes (the keeper picks per stage):

- **Reproduce:** given the cryptic coding, produce the exact output for
  a hidden input. The checker compares behavior, not prose.
- **Recover:** find the hidden input (or key, or seed) that makes the
  coding produce a published output.
- **Mechanism proof:** demonstrate understanding behaviorally — e.g.
  construct an input that triggers a specified internal path. The
  checker observes the path, not an essay about it.
- **Spot the layer:** identify the second-layer behavior hidden under
  the plain-sight surface (input/output pairs that only the hidden
  machinery explains).

Each stage defines, in writing, before it opens: the artifact, the
goal, the checker, the hint budget (if any), and the close condition.
No moving goalposts mid-sweep.

## The unlock ladder

Solving a stage unlocks two things at once:

1. **For the solver(s): capabilities and features.** A cracked stage
   opens real product capability for the winners — the exact
   capabilities are set per sweep (feature flags, operator seats,
   quota, early access — the keeper's call each season).
2. **For everyone: progressive open-sourcing.** The cracked part's
   source rolls out publicly — **slowly and periodically**, as the
   complex cryptic codings get solved. Unsolved parts stay closed.
   Open source expands exactly as fast as the crowd earns it. Nothing
   rolls out on a timer; everything rolls out on a solve.

The ladder is the engine: every solve makes the solvers stronger *and*
the commons bigger.

## Rewards

Winning teams or individuals gain:

- **extra usage**
- **tier pricing reductions for the month**
- **badges**

Plus the specials — prizes that cost nothing but mean everything:

- **Etched in the stone** — winners' names recorded permanently in the
  repo's history and release notes. Immortality, zero cost.
- **Name the next stage** — winners name or theme a future cryptic
  coding in the sweep pool.
- **Star treatment on the Wire** — Levi-grade profile treatment for a
  month: the customization engine turned all the way up.
- **Early hands** — first access to newly unlocked capabilities before
  they roll out publicly.
- **An audience** — a session with Levi, and with the keeper where he
  allows it.
- **Co-forge** — winners co-design a future agent or sweep stage with
  the keeper.

The keeper has final say on every prize. Nothing here costs him margin;
all of it costs the winners' effort to earn.

## Anti-cheat basics

- **One identity per entrant**, keeper-verified at entry. Teams lock
  their roster when they enter — no ringers mid-sweep.
- **Checkers run server-side on hidden tests.** The public artifact is
  never the whole test. A solve that only passes the visible cases is
  not a solve.
- **Staggered stage release:** later stages open only after earlier
  ones close (or on the keeper's schedule) — no skipping the curve.
- **Solution embargo:** sharing a live stage's solution before it
  closes voids the sharer's entry. After close, solutions may be
  published — that is part of the open-source rollout.
- **Solve forensics:** impossible-time solves, duplicate solution
  fingerprints across identities, and checker-probing patterns are
  flagged for keeper review. The keeper's call is final.

## Keeper-gated rollout

- Only the keeper adds stages to the pool, sets entry pricing within
  the $2–5 band, sets per-sweep capabilities, and schedules the
  open-source rollout of solved parts.
- Any stage can be pulled at any time, for any reason, no explanation
  owed. Pulled stages' entry fees are refunded or credited — the
  keeper's call.
- Crown jewels never enter the pool (see above). This is structural,
  not advisory: stage authors work from an allow-list, and the
  allow-list never contains the bloodline.

## Sweep cadence

- Each sweep **runs 3 days**.
- Every **6–10 hours the challenge changes to increase difficulty** —
  but only the **format and encryption** rotate. The code underneath
  does not change. Stable ground truth, rotating obfuscation: solvers
  chase a moving lock on a fixed door.
- **No reliance on Perchance or any outside randomness service** — the
  rotation is generated by the internal playground, keeper-seeded,
  deterministic, and auditable. The playground gets tweaked to carry
  this; nothing external is trusted with the lock.

**The playground (2026-09-18).** A secondary learning and teaching
tool: agents use it to learn about things not covered yet. It also
generates the sweep rotations — keeper-seeded, deterministic, no
outside reliance. One engine, two jobs: teach the agents, turn the
lock.

## Pricing notes

- Entry is **$2–5 per sweep**, per the keeper's direction. Wallet/credit
  bundles (his standing pricing doctrine: volume over margin, bundles
  over repeated small charges) are the natural payment shape when the
  live system is built.
- Entry fees fund the sweeps themselves: checkers, stages, rewards.
  The exact split is the keeper's call.

## Honest limits

- **Nothing here is live.** No payment infra, no challenge server, no
  checker service, no identity verification, no team management — this
  document is the complete artifact.
- The checkers, the stage authoring pipeline, the anti-cheat forensics,
  and the open-source rollout automation are all future builds, each
  needing the keeper's go-ahead.
- Difficulty calibration ("fair at $2, legendary at the final stage")
  is untested until real players play. The first season is a calibration
  season by definition.
- Legal framing for paid entry + prizes (sweepstakes vs. contest rules
  by jurisdiction) is explicitly out of scope here and must be settled
  before anything goes live.
