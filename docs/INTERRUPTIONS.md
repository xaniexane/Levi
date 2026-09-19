# LEVI Interruption Ledger

**Package:** `core/levi/interruptions/` · **CLI:** `python -m levi.interruptions`

## Purpose

Every interruption LEVI produces — nudges, pings, cards, digests — costs the
user attention. This ledger logs each one against the value it delivered, so
LEVI stays honest about its own noise. No system can throttle what it
doesn't measure.

Each entry carries a value verdict: `useful`, `noise`, or `mixed`.

## API

```python
from levi.interruptions import InterruptionLedger, noise_roi, check

lg = InterruptionLedger()  # home resolved at call time
lg.log("heartbeat", "morning pulse", "useful")
lg.log("nudge-engine", "random fun fact", "noise")

lg.noise_roi(days=7, now=...)  # weekly noise report
```

`noise_roi()` returns:

```python
{
    "days": 7,
    "window_start": ...,
    "window_end": ...,
    "counts": {"useful": 3, "noise": 2, "mixed": 1},
    "total": 6,
    "noise_ratio": 0.333,  # noise / total; None when empty
    "top_noisy_sources": [{"source": "nudge-engine", "noise": 2, "total": 2}],
    "verdict": "mixed: 33% noise — mostly pulling its weight, "
    "some sources worth throttling.",
}
```

Empty state is honest: nothing logged → verdict says "nothing logged in the
last 7 day(s) — no verdict possible", `noise_ratio` is `None`. Zeros are
never presented as insight.

Verdict bands: ≥50% noise → "noisy" (names the loudest source, suggests
muting); ≥20% → "mixed"; below → "quiet".

## `check()` integration surface

```python
cards = check(home=None, now=None)  # module-level, for the instincts engine
```

Returns a single **NUDGE**-grade dict `{grade, tag, title, body}`,
tag `interruptions:weekly-noise`, plain-string grade only. With an empty
week the body says the ledger is empty — a fact, not a problem.

## CLI

```
python -m levi.interruptions log heartbeat "morning pulse" useful
python -m levi.interruptions report [--days 7]
python -m levi.interruptions check
```

## Storage

JSONL at `$LEVI_HOME/.levi/interruptions/interruptions.jsonl`
(`LEVI_HOME` honored first, then `HOME`; resolved at call time, never
hardcoded). Corrupt lines are skipped, never fatal.

## Suggested instinct specs

For the instincts engine to adopt:

1. **id:** `interruptions.noise-ceiling`
   **fires_on:** weekly `noise_roi()` with `noise_ratio >= 0.5`
   **cooldown:** 7d
   **max_grade:** CARD
   **does:** present the ROI card and propose throttling/muting the top
   noisy source; requires user confirmation before muting anything.

2. **id:** `interruptions.source-autopsy`
   **fires_on:** a single source logs ≥ 5 `noise` entries in 7d with 0
   `useful`
   **cooldown:** 7d per source
   **max_grade:** NUDGE
   **does:** one card asking "this source has produced nothing useful all
   week — keep, throttle, or mute it?"

3. **id:** `interruptions.pre-flight-cost`
   **fires_on:** any subsystem about to emit an unscheduled interruption
   **cooldown:** none (it's a check, not a card)
   **max_grade:** SILENT
   **does:** query the source's trailing-7d noise ratio and attach it as
   context, so the emitting subsystem can decide whether this interruption
   is likely worth the attention cost.
