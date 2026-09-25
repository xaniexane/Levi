---
skill_id: compressed.engine-season
name: Season Pattern
description: Read the last 14 days of activity and name the season — surge, steady, or rest — with the next rest counted down.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, rhythm, rest, pacing]
version: 1.0.0
---
# Season Pattern

## Purpose

LEVI never stops, but the keeper is human, and rest is load-bearing.
The season pattern reads fourteen days of activity — events per day —
and names the current season: *surge* (load high, rest kept pace, the
window is open), *steady* (neither strain nor slack), or *rest* (the
stretch ran hot and rest fell short). It names the weather; it never
grounds the plane. Advisory only, always.

## When to use

- Weekly planning: is this a surge week or a recovery week?
- After a heavy stretch — check whether rest fell short before
  scheduling the next push.
- Retrospectives on pacing: did the quiet days actually happen?
- Run it through the `season` engine (`levi engines run season`).

## The pattern

1. **Gather fourteen daily loads**, oldest first. A load is a simple
   event count for the day — don't over-measure. Zero is a quiet day;
   say so honestly instead of padding it.
2. **Name the season.**
   - Hot stretch (avg >= 3/day) *and* quiet days short of target →
     **rest**: take a quiet day before the next surge.
   - High load (avg >= 6/day) *and* rest kept pace → **surge**:
     the window is open, spend it.
   - Otherwise → **steady**: hold the pace.
3. **Read the countdown.** `next_rest_due_days` says how soon a quiet
   day is due; 0 means now. Put it on the calendar, not in the notes.
4. **Act at the season's strength.** A rest season is not permission
   to surge anyway — the pattern fails silently if the verdict is
   overridden every time it inconveniences the plan.

## Anti-patterns

- **Padded zeros:** calling a day with six meetings "quiet" because
  nothing shipped. Quiet means zero events; the engine counts honest zeros.
- **Season denial:** asking for a re-read with different thresholds
  until the answer is "surge". The thresholds are parameters, not a
  slot machine — changing them changes the meaning, not the weather.
- **Rest debt rollover:** carrying "rest due in 0 days" for a week.
  Rest debt compounds like any other; a season engine read a week old
  is stale weather.
