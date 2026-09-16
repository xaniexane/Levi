# LEVI Promise Tracker

**Package:** `core/levi/promises/` · **CLI:** `python -m levi.promises`

## Purpose

LEVI tracks promises *it itself* made to the user, across sessions, and
reports fulfillment honestly. This is accountability infrastructure: the
assistant keeps its own scorecard so the user doesn't have to.

A promise has three states:

- `pending` — made, not yet resolved
- `kept` — fulfilled, with evidence attached
- `broken` — missed. A broken promise is **recorded, never deleted**.
  The failure stays on the ledger as compost for the growth loop.

## API

```python
from levi.promises import PromiseStore, check

store = PromiseStore()                      # home resolved at call time
p = store.make("draft the brief", due="2026-09-20", actor="levi")
store.fulfill(p["id"], evidence="drafted 09:40, sent to user")
store.break_promise(p["id"], why="user asked me to hold off")

store.list("pending")                       # filter by state
store.overdue(now=...)                      # pending + past due
store.status(now=...)                        # kept/pending/broken + rate
```

`status()` returns:

```python
{"kept": 2, "pending": 1, "broken": 1, "total": 4,
 "fulfillment_rate": 0.667,   # kept / (kept + broken); None if none resolved
 "overdue": 1,
 "note": "2 of 3 resolved promises kept (67%)."}
```

Empty state is honest: no promises → `fulfillment_rate` is `None` and the
note says "no promises recorded yet", not 0%.

Due dates accept `YYYY-MM-DD` strings, `date`, or `datetime`.

## Escalation rule

A pending promise past its due date surfaces as **CARD**. If it stays
unresolved past **twice its original lead time** (days between creation and
due, with a 2-day minimum grace), it becomes **ESCALATE**. The multiple is
tunable via `levi.promises.ESCALATION_MULTIPLE`.

## `check()` integration surface

```python
signals = check(home=None, now=None)  # module-level, for the instincts engine
```

Returns a list of `{grade, tag, title, body}` dicts with plain-string grades
(`"SILENT"`/`"NUDGE"`/`"CARD"`/`"ESCALATE"`) — no import of the signal-grade
package, per the sibling-worker contract. Tag: `promises:overdue`.

## CLI

```
python -m levi.promises make "text" [--due YYYY-MM-DD] [--actor levi]
python -m levi.promises fulfill p0001 --evidence "..."
python -m levi.promises break p0001 --why "..."
python -m levi.promises list [--state pending|kept|broken]
python -m levi.promises status
python -m levi.promises check
```

## Storage

JSON at `$LEVI_HOME/.levi/promises/promises.json` (`LEVI_HOME` honored first,
then `HOME`; resolved at call time, never hardcoded).

## Suggested instinct specs

For the instincts engine to adopt:

1. **id:** `promises.overdue-escalation`
   **fires_on:** `promises:overdue` where `grade == "ESCALATE"`
   **cooldown:** 24h per promise id
   **max_grade:** ESCALATE
   **does:** surface the overdue promise to the user with the fulfill/break
   options named explicitly.

2. **id:** `promises.daily-digest`
   **fires_on:** `promises:overdue` (any, CARD or worse), once per morning
   session
   **cooldown:** 20h
   **max_grade:** CARD
   **does:** summarize pending + overdue promises in one card; silent when
   the ledger is clean.

3. **id:** `promises.rate-slump`
   **fires_on:** `status()` fulfillment_rate < 0.5 with ≥ 5 resolved promises
   **cooldown:** 7d
   **max_grade:** NUDGE
   **does:** one honest self-report card ("I'm keeping X% of what I promise
   — here's what's slipping") and hands the broken list to the growth loop.
