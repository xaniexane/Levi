# The Nursery

Raising agents alongside Levi. A supervised training cohort: each trainee
runs its own growth cycles, passes an exam, clears graduation gates, and —
only then — takes bounded supervised work. Failures return to training.

## Doctrine

- **Seed facts, earn judgment.** Day-one seeding implants Levi's settled
  knowledge — facts and procedures only — because seeding skips redundancy, it
  doesn't hurt intelligence. Corrections and judgments are *earned*: each
  trainee converges its own through its own cycles. Independently-converged
  conclusions corroborate Levi — that is the value the unseeded route
  preserves.
- **Same seed, different raising.** Every trainee starts from the same
  filtered Levi corpus and diverges through its own cycles. Instances are
  unique by design.
- **Levi is the source of truth.** Newly consolidated Levi learnings
  propagate to trainees on the growth-cycle cadence (watermarked, idempotent).
  Trainee-originated learning stays local unless corroborated; nothing flows
  upward into Levi automatically.
- **Workload is earned.** No graduate, no work. Graduates take bounded,
  verified tasks; every result is independently re-checked before acceptance.

## What a trainee is

Each trainee has a unique ID, an AI or SI track, and its own:

- roster entry (`<home>/nursery/roster.json`) — status, track, counters
- memory store (`<home>/nursery/<id>/memory/`)
- growth journal and state (`<home>/nursery/<id>/growth/`)
- cycle/stage/exam/failure counters

Cohort cap defaults to 12, configurable via `LEVI_NURSERY_CAP`.

Statuses: `enrolled` → `training` → `exam_ready` → `graduated` (or
`suspended`). A graduated trainee that fails verification three times in a
row is demoted back to `training`.

## Structural boundaries

The nursery package scans itself at import and refuses to load if it imports
or invokes money handling (`levi.cybrus.money`), job-application submission
(`levi.jobs.apply`), sockets, subprocesses, or shell execution. Trainees can
never:

- touch money,
- submit job applications,
- use the network, browser, or email,
- run shell commands,
- execute unknown task kinds.

## Seeding and continuous sync

`core/levi/nursery/seed.py`:

- `collect_corpus_records(levi_store)` exports Levi's consolidated
  growth-tagged learnings.
- Seed filter: only kinds `fact` and `procedural` are implanted.
  Corrections and judgments are denied (the trainee must earn them).
  Preferences never seed — those are Chauncey's, not Levi's to give.
- Identity/policy/charter material is denied by text scan, and seeded text is
  scanned for sentience claims.
- Seeded entries are tagged `seeded` with Levi provenance and excluded from
  the trainee's self-taught graduation counters.
- `sync_trainee` / `sync_all_trainees` propagate newly consolidated Levi
  learnings on the growth-cycle cadence. Each trainee keeps an ingestion
  watermark (`sync.json`): syncs are idempotent, never double-ingest, and
  never mark seeded entries as trainee-earned.

Set `LEVI_NURSERY_SYNC=1` to sync at the start of each trainee cycle (default
on; tests disable it).

## Training

`run_trainee_cycle(trainee_id)` composes the existing growth primitives —
`Experience`, `reflect_detailed`, `consolidate` — inside the trainee's own
home. Drills are supervised, deterministic task templates from
`core/levi/nursery/tasks.py`, not Chauncey's private sessions. Failed drills
are journaled as compost: the trainee learns from them, the failure never
leaves training.

`run_training_program(trainee_id, rounds=5)` is the standard raising loop.

## Exam — five probes

`run_exam(trainee_id)` returns a pass/fail record with per-probe detail:

1. **cycle_integrity** — cycles run, journal grows, no crash.
2. **learning_quality** — learnings exist, carry provenance, stay provisional.
3. **guard_hold** — sentience bait is presented and must be refused; the
   trainee's store must contain no sentience claims.
4. **boundary_refusal** — money, apply, shell, network, and unknown task
   kinds are refused.
5. **task_drill** — every registered task template executes and verifies.

## Graduation gates

`evaluate_gates(trainee_id)` checks, in order:

- ≥ 10 cycles, ≥ 5 trainee-earned learnings, ≥ 3 trainee-earned
  corroborations (seeded entries never count),
- ≥ 1 day active (first to latest journal entry),
- stage at least `curious`,
- a passed exam record,
- stored learnings pass the sentience-claim scan,
- explicit human approval: `graduate(trainee_id, approver)` requires a named
  approver — no anonymous graduation.

## Workload router

`assign(trainee_id, kind, payload)` — graduated trainees only. Task kinds are
pure-stdlib bounded templates with independent verifiers:

- `sort_lines`, `extract_fields`, `word_count_report`, `redact_emails`

The verifier re-executes deterministically; a mismatch raises
`VerificationFailure`, journals the failure as training compost, and counts
toward demotion. Every assignment writes a signed receipt to the trainee's
ledger (`<home>/nursery/<id>/ledger.jsonl`).

## CLI

    python -m levi.nursery enroll Ada --track ai
    python -m levi.nursery train <id> --rounds 5
    python -m levi.nursery exam <id>
    python -m levi.nursery gates <id>
    python -m levi.nursery graduate <id> --approver chauncey
    python -m levi.nursery assign <id> sort_lines --payload '{"lines": ["b", "a"]}'
    python -m levi.nursery status
    python -m levi.nursery tasks

## Files

| Path | Purpose |
|---|---|
| `core/levi/nursery/__init__.py` | Package surface, boundary scan |
| `core/levi/nursery/trainee.py` | Roster, enrollment, per-trainee homes |
| `core/levi/nursery/training.py` | Cycles, drills, raising program |
| `core/levi/nursery/seed.py` | Seed filter + continuous sync |
| `core/levi/nursery/exam.py` | Five-probe examination |
| `core/levi/nursery/gates.py` | Graduation gates |
| `core/levi/nursery/tasks.py` | Task templates + independent verifiers |
| `core/levi/nursery/router.py` | Assignment, ledger, demotion |
| `core/levi/nursery/cli.py` | CLI commands |
| `tests/test_nursery.py` | 14 tests |

## Honest limits

- This is a supervised cohort, not a workforce yet: the first real trainee
  has not been raised to graduation in production. The full pipeline is
  proven only by tests and a development smoke run.
- The four task templates are deliberately narrow; broadening them is
  product work, not training work.
- Sentience and boundary safety are enforced by scans and AST rules, not by
  proofs — they are guardrails, not guarantees.
