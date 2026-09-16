# Jobs tracker

Local-first opportunity / deal pipeline tracker (`core/levi/jobs/`).
Originated in the Omega source-sync as a job-application pipeline built
from an empty spreadsheet template (see `docs/SOURCE_SYNC_PROTOCOL.md`
and `sync/sources.yaml`); it has since grown into the organism's general
pipeline tracker — the place DemandPulse opportunities land when you
decide to work them.

## Honest contract

- **Tracking only.** This records *your* pipeline. It does not scrape
  listings, contact anyone, or apply anywhere. Applications and outreach
  are always your action.
- **Local only.** State lives in `~/.levi/jobs/jobs.json` (atomic
  writes, owner-only permissions). Nothing leaves the machine.
- **Fixed pipeline.** Statuses are `new → active → won / lost /
  dropped`, with `won` / `lost` / `dropped` terminal. Moves are validated
  against an explicit transition map; statuses cannot be invented
  silently.
- **Demand honesty.** Anything imported from the demand pipeline is
  labeled HYPOTHESIS in its notes until verified — the tracker never
  invents market data.

## The status pipeline

```
new ──→ active ──→ won
 │         ├────→ lost
 └────────┴────→ dropped
```

Terminal states can be reopened back to `active` or `new` — a move never
deletes anything. Every other jump is rejected with an explicit error
(`new → won` is refused: work it first).

| Status   | Meaning                           |
|----------|-----------------------------------|
| `new`    | Captured, not yet worked          |
| `active` | Being pursued right now           |
| `won`    | Landed (terminal)                 |
| `lost`   | Pursued, didn't land (terminal)   |
| `dropped`| Deliberately abandoned (terminal) |

## Records

Each job carries: `id`, `title`, `company` (optional counterpart),
`source` (`manual` by default, `demand-pipeline` for imports), `status`,
timestamped `notes`, `created_at` / `updated_at`. A separate
`restrictions` list holds pipeline constraints (e.g. "local-first
only") — your stated constraints, not enforced filters.

## Storage & permissions

`~/.levi/jobs/` is created mode `0700`, `jobs.json` written mode `0600`
(owner-only, POSIX; best-effort elsewhere). Writes go through temp-file
+ atomic rename, so a crash can't corrupt the store; a corrupt store
loads as empty rather than crashing.

Migration: the previous single-file store (`~/.levi/jobs.json`) and the
old job-application stages migrate automatically on first load:
`review_buffer`/`applied` → `new`, `interview`/`prep` → `active`,
`offer` → `won`, `rejected` → `lost`, `withdrawn` → `dropped`.

## CLI

```bash
# from ~/workspace/levi/core
python -m levi.cli.main jobs add --title "Compost route" --company "Green Block" --source manual
python -m levi.cli.main jobs list
python -m levi.cli.main jobs list --status active
python -m levi.cli.main jobs move 1 active
python -m levi.cli.main jobs update 1 --title "Compost route v2"
python -m levi.cli.main jobs note 1 "Pilot block confirmed for Thursday"
python -m levi.cli.main jobs show 1
python -m levi.cli.main jobs restrict add "local-first only"
python -m levi.cli.main jobs stats
python -m levi.cli.main jobs import-demand --min-worth 0.5 --dry-run
```

With no subcommand, `levi jobs` prints `stats`.

## Demand pipeline → jobs

`levi jobs import-demand` reads the DemandPulse store
(`~/.levi/demand_pulse.json`) — read-only, never modified — and upserts
each opportunity and five-factor score card as a tracked job with
`source="demand-pipeline"` and status `new`. This is the least-invasive
integration: all new code lives in `core/levi/jobs/`; the demand
subsystem is untouched.

The import is **idempotent**: re-running it refreshes `updated_at` and
appends only new evidence notes instead of duplicating jobs. An
opportunity and a score card sharing a title merge into one job dossier
carrying both notes. Flags: `--dry-run` to preview, `--min-worth`
(0–1) / `--min-score` (0–100) to filter weak items, `--limit` to cap the
batch.

Typical flow:

```bash
levi demand --scan "neighbors want compost pickup" --title "Neighborhood compost pickup"
levi jobs import-demand            # track it
levi jobs move 1 active            # start working it
levi jobs note 1 "pilot block confirmed"
levi jobs move 1 won               # landed
```

## Python API

```python
from levi.jobs.tracker import JobTracker, import_demand

t = JobTracker()  # ~/.levi/jobs/jobs.json
job = t.add("Compost route", source="manual")
t.move(job.id, "active")                      # validated transition
t.note(job.id, "first pickup Thursday")
job, created = t.upsert("Compost route")      # idempotent add-or-refresh
t.update(job.id, status="won")
import_demand(t, min_worth=0.5)               # pull in demand opportunities
```

## Skills

Registered in `SkillRegistry` (category `productivity`):
`jobs_add` (INFO), `jobs_list` (INFO), `jobs_move` (LOW).

## Module map

```
core/levi/jobs/
├── __init__.py
├── tracker.py   JobTracker: JSON persistence, statuses + transition map,
│                notes, restrictions, stats, upsert, legacy migration,
│                import_demand(); JOB_SKILLS list
└── cli.py       register_jobs_parser() + cmd_jobs() (wired into
                 core/levi/cli/main.py)
```
