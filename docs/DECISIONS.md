# LEVI Decision Journal (with expiry)

**Package:** `core/levi/decisions/` · **CLI:** `python -m levi.decisions`

## Purpose

Decisions rot. This journal gives every recorded decision an **expiry in the
form of a revisit date**: when the date arrives, LEVI is asked "does this
still hold?" — reaffirm it with a note, or retire it with a reason.

- `reaffirm(id, note)` — still holds. The reasoning is annotated, not
  rewritten.
- `retire(id, why)` — no longer holds. Retired decisions are **composted**:
  kept on the journal with the reason, never deleted.

## API

```python
from levi.decisions import DecisionJournal, check

j = DecisionJournal()                        # home resolved at call time
d = j.decide("cache news for 24h", "freshness vs cost", revisit="2026-10-15")
j.reaffirm(d["id"], note="still the right trade — bandwidth costs real money")
j.retire(d["id"], why="user asked for live feeds; cost no longer the driver")

j.due_for_revisit(now=...)                   # active decisions with revisit <= now
j.list("retired")                            # the compost heap
j.status(now=...)                             # active/retired/due counts
```

Revisit dates accept `YYYY-MM-DD` strings, `date`, or `datetime`.

## `check()` integration surface

```python
signals = check(home=None, now=None)  # module-level, for the instincts engine
```

Returns a list of `{grade, tag, title, body}` dicts. Every revisit-due
decision is a **CARD** ("does this still hold?"), tag `decisions:revisit`,
plain-string grades only (no import of the signal-grade package).

## CLI

```
python -m levi.decisions decide "title" --reasoning "..." --revisit YYYY-MM-DD
python -m levi.decisions reaffirm d0001 --note "..."
python -m levi.decisions retire d0001 --why "..."
python -m levi.decisions list [--state active|retired]
python -m levi.decisions status
python -m levi.decisions check
```

## Storage

JSON at `$LEVI_HOME/.levi/decisions/decisions.json` (`LEVI_HOME` honored
first, then `HOME`; resolved at call time, never hardcoded).

## Suggested instinct specs

For the instincts engine to adopt:

1. **id:** `decisions.revisit-prompt`
   **fires_on:** `decisions:revisit`
   **cooldown:** 24h per decision id (a dismissed revisit snoozes, it doesn't
   vanish — the card returns until reaffirmed or retired)
   **max_grade:** CARD
   **does:** show the decision, its original reasoning, and offer two
   one-tap actions: "still holds" (prompts for note) / "retire" (prompts
   for why).

2. **id:** `decisions.stale-sweep`
   **fires_on:** weekly cron; decisions past revisit + 30d still unanswered
   **cooldown:** 7d
   **max_grade:** NUDGE
   **does:** one card listing all long-overdue revisits; nudges toward
   reaffirm-or-retire so the journal doesn't rot.

3. **id:** `decisions.pre-action-recall`
   **fires_on:** agent about to act in a domain with an active decision whose
   title matches the domain
   **cooldown:** per session
   **max_grade:** SILENT
   **does:** inject the decision + reasoning into context silently, so LEVI
   acts consistently with its own past calls.
