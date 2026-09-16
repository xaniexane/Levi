# Jobs — Hybrid Search & Apply tracker

Local-first job-application pipeline tracker (`core/levi/jobs/`).
Built from scratch during the Omega source-sync: the source repo
carried only an *empty spreadsheet template* whose sheet names sketched
this system (Review Buffer → Jobs → Interviews → Prep, Restrictions),
so the port is a **build**, not a copy — see
`docs/SOURCE_SYNC_PROTOCOL.md` and `sync/sources.yaml`.

## Honest contract

- **Tracking only.** This records *your* search. It does not scrape
  listings, contact employers, or apply anywhere. Applications are
  always your action.
- **Local only.** State lives in `~/.levi/jobs.json` (atomic writes).
  Nothing leaves the machine.
- **Fixed pipeline.** Stages are `review_buffer → applied → interview
  → prep → offer`, with `rejected` / `withdrawn` as terminal exits.
  Moves are validated; stages cannot be invented silently.

## CLI

```bash
# from ~/workspace/levi/core
python -m levi.cli.main jobs add --title "Backend Engineer" --company "Acme" --source "referral"
python -m levi.cli.main jobs list
python -m levi.cli.main jobs list --stage interview
python -m levi.cli.main jobs move 1 applied
python -m levi.cli.main jobs note 1 "Recruiter call went well; follow up Friday"
python -m levi.cli.main jobs show 1
python -m levi.cli.main jobs restrict add "remote only"
python -m levi.cli.main jobs restrict list
python -m levi.cli.main jobs stats
```

## Restrictions

Search constraints (`restrict add/remove/list`): e.g. `remote only`,
`no relocation`, `salary floor 120k`. They are recorded alongside the
pipeline and shown in `stats`; they are *your* stated constraints, not
enforced filters — the tracker does not fetch listings, so there is
nothing to filter.

## Skills

Registered in `SkillRegistry` (category `productivity`):
`jobs_add` (INFO), `jobs_list` (INFO), `jobs_move` (LOW).

## Module map

```
core/levi/jobs/
├── __init__.py
├── tracker.py   JobTracker: JSON persistence, stages, notes,
│                restrictions, stats; JOB_SKILLS list
└── cli.py       register_jobs_parser() + cmd_jobs() (wired into
                 core/levi/cli/main.py)
```
