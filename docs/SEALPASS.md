# SEALPASS — the Cybrus signature seal pass

Plain words. Every sealed module is an organ of Levi — all of Legion is
Levi, one organism.

## What one pass is

A seal pass takes one target module and runs the full stack over it —
**KFX² → DemandPulse → Echo → Mandella → REIM → RIEM → Quetta-Pan** —
**5 iterations**. Each iteration:

1. proposes improvements,
2. scores them deterministically,
3. checks them against Chauncey's originals,
4. stakes the survivors under fog and records the phantoms,
5. composts whatever was rejected, with reasons,
6. lets the genome learn steering from the outcome,
7. applies the approved variants — keeping the module's own tests green
   after every application.

Every stage appends a signed, hash-chained seal to the owner-only ledger
at `~/.levi/cybrus/sealpass/` (`LEVI_HOME` honored). Tampering fails
closed. If an iteration yields no approved improvements, that is
recorded honestly as convergence — iterations are never filled with
invented work.

## The 7 stages

| # | Stage | What it does | Wiring |
|---|-------|--------------|--------|
| 1 | KFX² | absorb (read the module) → reverse (name what it does wrong via heuristics + AST facts) → improve (proposals) | **Adapted** — the method implemented natively in cybrus. The dynasty `kfx2` wave runner is eyes-only and is never touched. Improve machinery is Quetta-Pan's real heuristic rules. |
| 2 | DemandPulse | deterministic scoring of proposals: scan → score → surface, no vibes | **Adapted** in the pairing shape — `levi.demand.scoring` is market-domain; the seal scorer mirrors its discipline (basis-required factors, weighted composite, `explain()` audit) on proposal-domain factors |
| 3 | Echo | originals/lineage check: rejects proposals contradicting Chauncey's declared originals | **Adapted** — no engine does this; the registry lives here, sourced from `levi.provenance` and the standing laws |
| 4 | Mandella | stakes each surviving proposal under fog; records the phantoms (unchosen options that haunt the decision) | **Real** — `levi.organs.mandella.run_mandella` |
| 5 | REIM | composts rejected/failed proposals with reasons, append-only | **Real** — `levi.quetta_pan.reim.ReimCompost` |
| 6 | RIEM | genome steering: consult-before-generation + a sealed steering snapshot per iteration | **Real** — `levi.quetta_pan.riem.RiemGenome` |
| 7 | Quetta-Pan | applies approved improved variants: backup → write → evaluate (parse + the target's own tests) → rollback + compost on failure | **Real** — `levi.quetta_pan.engine.QuettaPanEngine.apply_suggestion` |

## The 7 laws, enforced in code

- **keeper's law / anticipation** — every stage result carries
  `anticipated` next-actions; findings route forward automatically.
- **originals-first** — Echo rejects anti-original proposals.
- **law → guard → prove** — each stage entry runs a concrete guard
  (`GuardError`); the proof is `tests/test_cybrus_sealpass.py`,
  honestly named (invariant demonstrations, never "formally proven").
- **no-cancellation** — the ledger is append-only (no delete API); no
  proposal may remove a public definition.
- **nothing-thrown-away** — timestamped backups, variant store,
  append-only compost; runs are archived, never deleted.
- **forward-motion** — a guard firing composts the failure with its
  reason and the pass continues; nothing stalls silently.
- **honesty over polish** — scores require a stated basis; convergence
  zeroes are recorded; this table states what's wired vs adapted.

## How to run it

Proving run (Build 4, already executed 2026-09-22):

```
cd ~/workspace/levi
PYTHONPATH=core python3 -m levi.cybrus.sealpass --preset build4 --iterations 5 --repo-root .
```

Coordinator command — seal-pass Builds 1–3 when they land (one command):

```
cd ~/workspace/levi
PYTHONPATH=core python3 -m levi.cybrus.sealpass --all-builds --iterations 5 --repo-root .
```

Or single targets / presets:

```
PYTHONPATH=core python3 -m levi.cybrus.sealpass --preset build1 --preset build2 --iterations 5 --repo-root .
PYTHONPATH=core python3 -m levi.cybrus.sealpass --target core/levi/cybrus/enforce.py --iterations 5 --repo-root .
```

Flags: `--threshold` (default 75), `--manual-approve` (hold
applications instead of applying stage-gate approvals),
`--levi-home` (override the ledger location).

## What the proving run found (Build 4, 2026-09-22)

- `subscriptions.py` it1: 2 proposals (PY_FSTRING, PY_LIST_COMP),
  both scored 62.25 < 75 → composted with reasons → genome learned.
- it2: same 2 proposed again (suppression needs ≥ 2 attempts per the
  documented genome policy) → composted → rules suppressed from it3.
- it3–it5 and all of `content.py`: zero findings — the genome had
  already learned these advisory-only rules fail the threshold.
- **Applied: 0. Honest zeroes.** Both findings are advisory-only
  (Quetta-Pan has no safe auto-fix for them); nothing was written,
  both target files byte-identical before/after. 81 sealed ledger
  entries, chain verified.
- Note: the genome's context key is coarse (`py`, by Quetta-Pan's
  documented design), so one file's learned rejections steer later
  files too. That is the documented policy working, not a bug —
  but it means the seal pass leans conservative across files.
- The ledger, compost, and genome live at
  `~/.levi/cybrus/sealpass/` (mode 0700). The first proving run (which
  double-counted rejections into the genome) is archived untouched at
  `~/.levi/cybrus/sealpass-archive/20260922_120358-double-learn-run/`.
