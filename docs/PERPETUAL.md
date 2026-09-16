# PERPETUAL — the engine that never stops

The "never stops" half of LEVI's capstone identity: **the thing that is
everything and never stops**. The Archive (`docs/ARCHIVE.md`) is the
"everything"; this is the "never stops".

Three mechanisms, all stdlib-only, all local-first:

## 1. Supervision — `core/levi/perpetual/supervise.py`

OTP supervision trees (revived from Erlang/OTP in `core/levi/revival/otp.py`)
around LEVI's three long-running local services:

| service | what it runs | interval |
|---|---|---|
| `levi-heartbeat` | `levi.daemon.heartbeat.run_heartbeat(force=True)` — the periodic self-check | 60 min |
| `levi-growth` | `levi.growth.cycle.run_cycle(use_model=False)` — offline growth tick | 6 h |
| `levi-automation` | due `SCHEDULE` bot automations with a parseable `interval_min` | 5 min tick |

Strategy is `one_for_one`; restart intensity is 5 restarts per 300 s —
exceeding it means the supervisor **gives up honestly** (child `DEFUNCT`,
supervisor stops) rather than spinning forever. Every crash becomes a
structured `CrashReport` persisted to `~/.levi/perpetual/crashes/`.

Everything is an adapter: this package never edits daemon, bot, or growth
code. Service callables resolve lazily at child start; a broken service
module is an ordinary child crash, never a silent fallback.

A live supervisor refreshes `~/.levi/perpetual/supervisor.alive` every 30 s
and removes it on shutdown — a stopped engine must never look alive.

Run it: `python3 -m levi.perpetual` has no daemonize; the long-run entry is
`supervise.run_forever()` (systemd unit or cron `@reboot`, see below).

## 2. The perpetual hunt — `core/levi/perpetual/hunt.py`

The hunt for forgotten knowledge, as procedure + state + handoff format.
State lives in `~/.levi/perpetual/hunt_state.json` (atomic, owner-only).

- `plan_next_hunt()` picks the next uncovered theme. Covered ground is
  embedded as exclusion lists (waves 1–3: 30 + 50 + 40 finds); a theme is
  never re-hunted unless *every* theme is covered, in which case the plan
  explicitly says "deeper vein". An in-flight wave is never double-planned.
- `record_hunt()` validates every finding as an `ArchiveRecord`
  (deny-closed: malformed, duplicate, or empty findings are refused and
  nothing is half-recorded), queues records for Archive ingest under
  `~/.levi/perpetual/pending/<wave>.jsonl`, and queues load-bearing /
  useful-pattern findings in `build_queue.jsonl` under the standing
  auto-approval. Inspirational finds stay in the Archive as inspiration,
  not build orders.

### The weekly hunt (activate manually — nothing is scheduled by default)

The hunt is performed by the assistant when the scheduled job fires. The
cron definition below is documentation; **no cron job is created by the
build** — the user activates the schedule.

```cron
# LEVI perpetual hunt — every Sunday 03:00 America/Chicago
0 3 * * 0 cd ~/workspace/levi && PYTHONPATH=core python3 -m levi.perpetual hunt-plan >> ~/.levi/perpetual/hunt.log 2>&1
```

**Instructions for the scheduled worker** (paste into the cron job's
prompt / runbook):

1. `PYTHONPATH=core python3 -m levi.perpetual hunt-plan` → read the next
   wave: theme, exclusions (never re-cover these), due date.
2. Perform the research as a deep-research subagent: 30–50 entries, each
   with what/when, the concrete ahead-of-its-time mechanism, the real
   reason it died, a revival recipe, one concrete local-first AI
   application, two source links, a value rating
   (load-bearing/useful-pattern/inspirational), and honest skepticism flags.
3. Write the report to `~/workspace/research_notes/<slug>/report.md`.
4. Convert entries to ArchiveRecord JSON (one object per line) in
   `findings.jsonl`. Required: `id` (`arch-<tag>-...`), `title`, `kind`
   (`software`|`method`|`technique`), `summary`, `mechanism`, `decline`,
   `revival_recipe`, `levi_application`; `sources` (http URLs); `rating`;
   `status`; `provenance` (`found_date`, `research_slug`).
5. `PYTHONPATH=core python3 -m levi.perpetual hunt-record <wave-id>
   findings.jsonl --slug <slug>` → validates (deny-closed), queues for
   Archive ingest, queues buildable items.
6. Build the load-bearing findings into LEVI (standing pre-approval:
   forgotten-software/method finds are auto-approved for building).
7. Report back: wave id, findings count, commit SHAs.

### Keeping the engine itself alive

```cron
# LEVI perpetual supervisor — restart at boot, and keepalive every 5 min
@reboot cd ~/workspace/levi && PYTHONPATH=core nohup python3 -c "from levi.perpetual.supervise import run_forever; run_forever()" >> ~/.levi/perpetual/engine.log 2>&1 &
*/5 * * * * pgrep -f "levi.perpetual.supervise" >/dev/null || (cd ~/workspace/levi && PYTHONPATH=core nohup python3 -c "from levi.perpetual.supervise import run_forever; run_forever()" >> ~/.levi/perpetual/engine.log 2>&1 &)
```

## 3. Pulse — `core/levi/perpetual/pulse.py`

The one-glance proof of life. `python3 -m levi.perpetual pulse`:

```
LEVI perpetual engine: ALIVE  (uptime 3d 4h)
services: levi-automation, levi-growth, levi-heartbeat
crashes: 2 total {levi-growth:2}
archive: 120 records | pending waves: wave-004
hunts: 3 waves completed | last wave-003 (40 findings) | next due 2026-09-22T...
token budgets: day:49912, session:8230
build queue: 17 findings waiting
```

Every source degrades honestly: a missing subsystem reads as
"unavailable"/"not-initialized", never as zero, never as an exception.

## Safety boundaries

- Supervision is local-only: restarts Python service loops; never retries
  remote calls, places orders, or sends messages.
- Hunts research and queue; building follows the standing auto-approval
  for forgotten knowledge only. Nothing here grants new capabilities.
- Crash reports may contain tracebacks — `~/.levi/perpetual/` is 0700,
  files 0600.

## Standing laws

**Hard-route law.** Where there's a cost, take the hard route. When a hunt
find carries a cost — a paid API, licensed software, a proprietary
dependency, a subscription — the hunt must never recommend paying. Instead
it plans a clean-room recreation: analyze the pattern, then rebuild it from
scratch, stdlib-only, local-first. This is enforced in the procedure, not
just the prose:

- the research brief (`plan_next_hunt`) and the worker handoff both carry
  the law verbatim;
- `hunt-record` runs `hard_route_review()` over every finding's revival
  recipe and LEVI application, flagging cost-bearing dependencies;
- flagged findings enter the build queue with `"hard_route": true` and an
  explicit clean-room-recreation note — the builder takes the pattern, not
  the price tag.

No paid APIs, no licensed dependencies, no tolls. LEVI costs its keeper
nothing and stays free to produce.

## Honest gaps

- The Archive store module is still landing; `pulse` counts durable
  record-shaped JSONL files and pending waves rather than querying a store
  API. It says what it counted.
- `run_forever()` is a foreground loop; real daemonization is the
  operator's systemd/cron (definitions above).
- Supervision covers threads, not processes (inherited from `otp.py`).
- The hunt's web research is done by the assistant at fire time — this
  package is the procedure, state, and handoff, not the researcher.
