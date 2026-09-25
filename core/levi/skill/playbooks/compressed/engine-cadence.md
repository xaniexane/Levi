---
skill_id: compressed.engine-cadence
name: Cadence Pattern
description: Read the rhythm of any timestamped series — detected vs expected period, streak, drift, and next-due.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, rhythm, scheduling, drift]
version: 1.0.0
---
# Cadence Pattern

## Purpose

Turn a pile of timestamps into a rhythm read: is this thing on beat,
slipping, or dead? Built for automation schedules, but it works on any
repeating series — check-ins, backups, doses, deliveries.

## When to use

- An automation should run every N hours; is it drifting?
- Streaks worth keeping visible (duolingo-style, without the guilt owl).
- Answering "when is this due next?" from raw history alone.
- Run it through the `cadence` engine (`levi engines run cadence`).

## The pattern

1. **Feed the event list.** ISO-8601 timestamps, any order; duplicates
   are dropped, not double-counted.
2. **Declare the expected period.** The engine measures *detected* vs
   *expected* — the gap between them is the interesting number.
3. **Read three signals:** on-time streak (how long the beat has held),
   missed beats (how many periods got swallowed), drift (hours overdue).
4. **Pin `now` for replays.** Pass an explicit reference time and the
   read is perfectly reproducible.

## Honest limits

- ±25% of the period counts as "on time". Real rhythms breathe; the
  engine allows for that instead of crying wolf.
- Fewer than two events means no rhythm — the engine says so with
  confidence 0.0 instead of inventing one.
- It reads rhythm, not cause. A broken streak tells you *that* the beat
  slipped, never *why*.
