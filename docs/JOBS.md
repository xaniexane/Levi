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
t.move(job.id, "active")  # validated transition
t.note(job.id, "first pickup Thursday")
job, created = t.upsert("Compost route")  # idempotent add-or-refresh
t.update(job.id, status="won")
import_demand(t, min_worth=0.5)  # pull in demand opportunities
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
├── cli.py       register_jobs_parser() + cmd_jobs() (wired into
│                core/levi/cli/main.py); dispatches `organ` to organ_cli
├── profiles.py  ENGINE law: one profile per human, deny-closed schema,
│                owner-only JSON. Chauncey's data is ONE profile here —
│                never a literal in engine code.
├── store.py     Warehouse: 19 workbook-sheet tables as JSON
│                (review_buffer … job_history_archive) + gig_offers,
│                gig_income; import_workbook() reads the V2 xlsx.
├── sourcing.py  ENGINE 1: Review Buffer intake — dedupe, blacklist
│                screen, hard-restriction screen; hypothesis-labeled.
├── triage.py    ENGINE 2: deterministic 1–10 scoring + promotion to
│                the Apply Queue at threshold.
├── apply.py     ENGINE 3: packet drafting/prefill; human authorizes
│                EVERY submission; log only on human-confirmed submit.
├── intel.py     ENGINE 4: company intel, watchlist, blacklist,
│                restrictions/filters.
├── prep.py      ENGINE 5: Prep Hub, Resume Map, Cover Letter Bank,
│                cover-letter factory (drafts only).
├── gig.py       Gig/fast-cash parallel track: offers, rule evaluation,
│                human-approved grabs, income tracker.
├── modes.py     Run modes: full / light / low-data / offline.
├── chains.py    Chained workflows: trigger → conditions → actions →
│                verification → receipt; to_flow() renders flows.py
│                manifests; chain_mermaid() for visualization.
└── organ_cli.py  `levi jobs organ …` surface (dry-run default).
```

---

# Universal Job Organ

A LEVI organ, not a spreadsheet port. Five compressed engines over the
warehouse whose schema is the recovered 19-sheet **Hybrid Job Search
and Apply System V2** workbook — every table mirrors one workbook
sheet, column for column.

## The five engines

| Engine | Module | Job |
|---|---|---|
| **Sourcing** | `sourcing.py` | Stages listings into the Review Buffer: dedupe, blacklist screen, hard-restriction screen. Everything ingested is labeled hypothesis until verified. |
| **Triage** | `triage.py` | Deterministic 1–10 match scoring with a published breakdown; promotes ≥ threshold into the Apply Queue. |
| **Apply** | `apply.py` | Builds submission packets (resume pick + cover-letter draft + prefill). Drafts and prefills only — never submits. |
| **Intel** | `intel.py` | Company intel, watchlist, blacklist, restrictions/filters. Local enrichment only; unknown companies report `intel: null`. |
| **Prep** | `prep.py` | Prep Hub (STAR scaffolds), Resume Map, Cover Letter Bank, and the cover-letter factory (drafts only, unknown placeholders stay visible). |

Parallel track: **gig / fast-cash** (`gig.py`) — gig offers, auto-accept
rule *evaluation*, human-approved block grabs, income tracker.

## Pipeline

```
Review Buffer → Apply Queue → Application Log
                     ↓
              Interviews → Offers / Decisions
```

Plus: Prep Hub, Resume Map, Cover Letter Bank, Skills Matrix, Job
Boards, Company Intel, Restrictions & Filters, Blacklist, Automation
Logs, Training & Courses, Job History Archive, gig_offers, gig_income.

## Binding laws (enforced in code)

1. **Universal engine, separate profiles.** `profiles.py` holds one
   record per human; engine code contains zero personal data. No profile
   → engines degrade honestly, never invent.
2. **The human authorizes EVERY actual submission.** `apply.py` drafts
   packets; the Application Log only gains a row after the human
   *confirms* they submitted (`log_submission` refuses on dry-run or
   denial). The organ is never the hand on the button.
3. **Dry-run is the default** for every engine, chain, and CLI command.
   Live execution is an explicit per-call choice and still gates.
4. **Board scraping is not built.** The organ consumes listing dicts
   (local files, workbook, human paste). Fetching is the human's
   browser or a browser agent's job.

## Scoring rubric (1–10, deterministic)

Base 1, plus: role fit +3 · pay fit +2 · remote fit +2 · skills overlap
+2 · equipment +1. Hard caps at 2: avoided job type matched; record
needs felony-friendly and the listing is not. Every score ships its
breakdown.

## Chained workflows

`chains.py`: **trigger → conditions → actions → verification → receipt**.
Four built-ins: `morning-sweep`, `apply-packet`, `interview-prep`,
`gig-watch`. Each chain renders a `levi.automation.flows`-compatible
manifest (`to_flow` / `chain_mermaid`) — predicate/emit/note nodes,
valid per `build_flow`.

**Seam (honest):** flows.py `minion` nodes must reference the signed
automation catalog, and job actions aren't catalog minions — so the flow
manifest is the *map* (visualizable), while the native `run_chain` is
the *territory* (executable). If a sibling registers `jobs.*` minions in
the catalog later, the manifests become executable via `run_flow` as-is.
No sibling chain framework was found in the repo; this is noted, not
assumed.

## Interaction modes (via `levi.automation.hitl`)

notification · dialog · approval · edit-and-approve · acknowledge ·
confirm. Gates resolve through an injected responder — dry-run
simulates, live CLI asks on stdin, tests inject `auto_approve` /
`auto_deny`.

## Run modes

`--mode full` (default) · `light` (read-only) · `low-data` (local work
only, no external enrichment) · `offline` (hard no-network posture).

## CLI

Organ-level flags (`--profile`, `--mode`, `--live`) come **before** the
engine name. Dry-run default: add `--live` to execute.

```bash
# profiles (Chauncey's data is ONE profile, filled by him, never hardcoded)
levi jobs organ --live profile create chauncey --scaffold
levi jobs organ --live --profile chauncey profile set chauncey phone "217-610-0636"

# warehouse from the recovered workbook
levi jobs organ --live workbook import --path "/path/to/Hybrid Job Search and Apply System V2 (Master – Clean) (2).xlsx"

# pipeline
levi jobs organ sourcing ingest --file listings.json --board indeed
levi jobs organ --profile chauncey triage run --threshold 7
levi jobs organ --live --profile chauncey apply draft --queue-id 1
levi jobs organ --live --profile chauncey apply authorize --queue-id 1   # human approves
# ... human submits on the board site ...
levi jobs organ --live --profile chauncey apply log --queue-id 1 --confirmed

# intel / prep / gig
levi jobs organ intel check --company "Acme" --title "Chat Agent"
levi jobs organ --live --profile chauncey prep packet --title "Chat Agent" --company "Acme"
levi jobs organ --live --profile chauncey gig offer-add --platform DashX --title "Dinner block" --pay 48
levi jobs organ --profile chauncey gig evaluate --min-pay 40 --max-dist 5

# chains
levi jobs organ --profile chauncey chain run morning-sweep --listings listings.json
levi jobs organ --profile chauncey chain flow apply-packet   # mermaid manifest

# dashboard
levi jobs organ --profile chauncey dash
```

## State

`~/.levi/jobs/`: `warehouse/*.json` (19 tables), `profiles/*.json`,
plus the pre-existing `jobs.json` tracker (untouched). Dir 0700, files
0600. The old `levi jobs` tracker commands are unchanged.

## Honest gaps

- No board scraping or auto-applying (by design, per the laws).
- No real gig-platform integration — the organ stages and evaluates; the
  human taps the grab in the gig app.
- Chain flow manifests aren't executable via `run_flow` until job
  minions exist in the automation catalog (seam documented above).
- `enrich_external` capability exists in the mode table but no external
  enrichment source is wired yet.
