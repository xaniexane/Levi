# LEVI Heartbeat

The heartbeat is LEVI's autonomous self-check: a periodic, offline, read-only
sweep of local state that surfaces anything needing attention — and stays
quiet when everything is fine.

## What it checks

Each run scans three sources (each guarded so one bad source can't crash the
run; a failing source becomes a single attention item):

1. **Growth learnings** — memory entries tagged `growth` with
   `metadata.status == "provisional"` (unreviewed), added since the last
   heartbeat. These come from the growth loop (`core/levi/growth/`) and land
   in `~/.levi/memory/index.json`.
2. **Pending tracked items** — automations in
   `~/.levi/automations/automations.json` that are:
   - active with a failed/errored last run,
   - active but stale (no run in 7+ days), or
   - drafts with actions configured but not yet activated.
3. **Recent errors** — error records in `~/.levi/agent/sessions/*.jsonl`
   from the last 24 hours.

## Behavior

- **Silent by default.** Clean run → one quiet line, no digest.
  Attention items → prints a short digest and saves it to
  `~/.levi/heartbeat/last_digest.md`.
- **Active hours:** 8:00–22:00 **local** time only. Outside that window the
  run is a no-op with reason `outside active hours`.
- **Interval:** default 30 minutes, configurable:
  - env var `LEVI_HEARTBEAT_INTERVAL_MIN`
  - `levi heartbeat run --interval-min 60`
  State (`~/.levi/heartbeat/state.json`) records the last run; a `run`
  inside the interval is a cheap no-op (`interval not elapsed`) unless
  `--force` is passed.
- **Cheap when idle:** read-only file scans, no model/provider calls, no
  network. Intended for a cron/systemd-timer entry, e.g.
  `*/10 * * * * levi heartbeat run` (the interval gate keeps it at 30-min
  effective cadence).

## CLI

```bash
levi heartbeat run            # one check (no-op inside the interval)
levi heartbeat run --force    # check even if inside the interval
levi heartbeat run --interval-min 60
levi heartbeat status         # last run, interval, active-hours window,
                              # attention count from the last digest
```

## Honest limits

- The checks are **heuristics, not deep reasoning**: "failed" is a
  substring match on `last_result`; "stale" is a fixed 7-day threshold;
  "overdue" is not schedule-aware (cron specs in `trigger_config` are not
  evaluated).
- The digest is **advisory** — it never takes action, never contacts the
  user, never spends resources. Acting on an item is a separate,
  human-gated decision.
- Only sources listed above are scanned; blind spots (vault state, cloud
  sync, news freshness) are out of scope for now.
- Active-hours gating uses the machine's local timezone.
