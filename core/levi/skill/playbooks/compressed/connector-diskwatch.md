---
skill_id: compressed.connector-diskwatch
name: Disk Watch Pattern
description: Poll local disk usage and raise exactly one event per usage-band change — warn, crit, and the recovery back to ok.
risk: info
permissions: []
requires_confirmation: false
tags: [connectors, observability, disk, polling]
version: 1.0.0
---
# Disk Watch Pattern

## Purpose

Give LEVI an ear on local disk health without a daemon: poll
`shutil.disk_usage`, compare against warn/crit bands, and emit exactly
one event when the band changes — including the recovery. A steady disk
is a quiet disk.

## When to use

Watching a volume that fills up: the corpus drive, the backup target,
the phone-sync staging dir. Pair it with the automation tick (poll on a
schedule) or call it before a big ingest — "is there room?" is a
question worth asking first.

## The pattern

1. **Poll with a path.** `registry.poll("diskwatch", path="~/workspace",
   state={})`. The path just needs to exist — usage is per volume, so
   any file or directory on that volume answers.
2. **Hold the state.** The connector returns `(events, new_state)`.
   Keep `new_state` and pass it back as `state` next poll. The
   connector keeps nothing itself — its memory is yours to hold.
3. **Set honest bands.** `warn_pct` (default 80) and `crit_pct`
   (default 95), deny-closed: 0 < warn < crit < 100. Set them where
   *action* changes: warn = "start the cleanup plan", crit = "stop
   ingesting now".
4. **Read the edges.** First poll emits a `baseline` event naming the
   current band — a watched disk is never silently assumed healthy. A
   band change emits one `band_changed` event with `prev_band`,
   `used_pct`, `free_bytes`. No change → no event. Recovery to `ok`
   emits too — the all-clear is an event, not an absence.
5. **Act outside the connector.** Connectors observe; they never act.
   The event goes to the automation engine or the keeper — the policy
   that cleans up lives there, not here.

## The laws

- **Observe-only:** the poll reads disk usage. It never writes, never
  deletes, never "fixes" the disk.
- **Stateless connector:** the last band lives in caller-held state.
- **Edge-only:** steady bands are silent; changes (and recoveries) are
  exactly one event each.

## Honest limits

- This is a snapshot poll, not a watcher — a disk that fills and drains
  between polls is never seen. Poll on a cadence that matches the
  risk.
- `used_pct` is volume-wide, not per-directory. It cannot tell you
  *what* grew — pair it with the directory connector for that.
- Thresholds are percentages; a 95% full 64GB phone and a 95% full 8TB
  array are different emergencies. Set bands per volume, not globally.
