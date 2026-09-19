# Dream Engine

The dream simulator kernel: recent history goes in as seed, forward
projections come out variated many ways. Failure branches are marked for
compost (REIM); survivors compress into heritable lessons (RIEM).

Mined from the Levi 30.x lineage uploads (DreamEngine / ImaginationDaemon /
Symbiote / TimeCapsule concepts); this is an original, offline-first,
stdlib-only implementation — not a port.

## Layout

- `core/levi/dream/engine.py` — `DreamEngine`: collect seeds (growth journal
  or injected), `synthesize_dream` per seed, journal the record.
- `core/levi/dream/vary.py` — variation transforms: invert, amplify,
  transplant, negate_constraint, compress. Pure functions, deterministic.
- `core/levi/dream/journal.py` — append-only JSONL dream journal at
  `~/.levi/dream/journal.jsonl` (owner-only).
- `core/levi/dream/cycle.py` — `run_cycle` / `run_nightly`: the full
  dream → REIM → RIEM cycle (see "Organism wiring").
- `core/levi/dream/symbiote.py` — `nudge()`: surface the freshest thread.
- `core/levi/capsule/` — TimeCapsule: `create_seed` / `inspect_seed` /
  `plant_seed` for portable `.lseed` state (dream + growth journals, merged
  with dedup — nothing overwritten blindly).

## Organism wiring

The kernel is wired into the organism's compost organs — no parallel APIs:

- **Dream compost → REIM.** Each cycle converts composted / risky dream
  branches into REIM failure records (`source="dream"`) and calls the real
  `levi.organs.reim.compost_failure`. Composted branches are severity
  "low", risky branches "medium" — dreams are simulations, never real
  failures, so nothing dreamt auto-escalates to "high". Batches are
  appended owner-only to `~/.levi/dream/compost.jsonl`.
- **Dream lessons → RIEM.** The surviving lesson (if any) is attached to
  each compost record's context, and the batch is offered to the real
  `levi.organs.riem.promote`. Eligible records (RIEM's promotion rule:
  `reusable` and corroborated or high severity) become genome proposals,
  written owner-only to `~/.levi/dream/riem_proposals.jsonl` as data —
  proposals are never applied.

## Nightly run

The daemon registers a nightly dream job in the automation registry
(`core/levi/daemon/automation.py`: `ensure_nightly_dream_job`), trigger
`schedule`, cadence nightly, runner `levi.dream.cycle:run_nightly`. It is
registered-but-inert by default: status `paused`, and `run_dream_job` is a
no-op unless `LEVI_DREAM_ENABLED=1`. Manual run:

```bash
python -m levi.dream cycle --limit 5
```

## Owner-only journal

Entries live under `~/.levi` (or `$LEVI_HOME`). `DreamJournal.append`
locks the journal to `0600` and its directory to `0700` via
`enforce_owner_only()`, and verifies the result with `owner_only_ok()`
(POSIX) — a failed lock raises instead of leaking. Cycle side files
(`compost.jsonl`, `riem_proposals.jsonl`) get the same treatment.

## Modes

Rule-based synthesis always works offline (`mode="rules"`). Pass a
`generate` callable for model-assisted dreams; the record honestly reports
`mode="model-assisted"` only when the model actually contributed.

## CLI

```bash
python -m levi.dream once --text "seed words here"
python -m levi.dream once --limit 5        # dream over recent growth journal
python -m levi.dream journal --last 10
python -m levi.dream nudge
python -m levi.dream cycle --limit 5       # full dream → REIM → RIEM cycle
```

## Cybrus additions (same pack)

- `core/levi/cybrus/capability.py` — `CapabilityRegistry`: explicit,
  discoverable capabilities with risk bands; `require()` is deny-closed.
- `core/levi/cybrus/evidence.py` — `EvidenceLedger`: digest-chained,
  sealed evidence records; `verify_chain()` detects tampering.

## Surgeon addition (same pack)

- `core/levi/surgeon/elite.py` — multi-pass heuristic repair
  (`elite_repair`): syntax-gated passes, rollback on parse breakage,
  snapshot-first via the existing `SnapshotManager`, `.elite.bak` beside
  the file. Adapted from the Omega Code Surgeon ELITE v3 concept.
