# Goal-Drift Instrument

**Notices when stated goals and actual behavior diverge over weeks.**
An honest instrument, not a judge: it compares the trailing-14-day
activity tag distribution against stated goals and raises a CARD only
when the evidence (counts, examples) supports it. Below threshold it
stays SILENT — no vague claims, ever.

## Purpose

Everyone drifts: the week you said was for deep work became novelty
and admin. Memory is unreliable about this; a counter is not. The
drift instrument gives LEVI a quiet way to surface the gap *with
receipts* instead of vibes.

## API

```python
from levi.drift import set_goal, log_activity, weekly_card

set_goal("ship-book", "Finish the book draft", tags=["deep-work", "writing"])
log_activity(["deep-work"], "drafted chapter 3")
log_activity(["novelty"], "doomscrolled the feed")

card = weekly_card()  # or weekly_card(now=datetime...) in tests
if card is None:
    print("SILENT")  # aligned — or too little data to say
else:
    print(card["grade"], card["tag"], card["title"])  # "CARD [drift] ..."
    print(card["body"])  # the evidence: counts + examples
```

### Firing rule (all three must hold)

1. **Enough data**: ≥ 5 activities logged in the trailing 14 days.
   Fewer → SILENT. Drift is never claimed on silence.
2. **A goal is starved**: the share of window activities carrying at
   least one of the goal's tags is below `DRIFT_THRESHOLD` (0.2).
3. **The behavior went somewhere concrete**: some tag claimed by *no*
   goal absorbed ≥ 5 entries — so the card can name it and show
   examples.

### Card shape

```python
{
  "grade": "CARD",
  "tag": "[drift]",
  "title": "Goal drift: behavior and stated goals diverged",
  "body": "... trailing-14-day counts, per-goal shares, where the time
           went, up to 5 concrete examples, and a non-judgmental close ...",
  "drifting_goals": ["ship-book"],
  "window_days": 14,
  "activity_count": 17,
}
```

The copy law: **evidence, not a verdict.** The card closes with
"This is evidence, not a verdict — adjust the goal or the week." No
shaming, no guilt framing.

Data lives in `<LEVI_HOME>/drift/goals.json` and
`<LEVI_HOME>/drift/activity.jsonl` — local JSON only. Home resolves at
call time (`LEVI_HOME` env → `~/.levi`); `now` is injectable.

## CLI

```
python -m levi.drift set-goal ID --statement "..." [--tag T ...]
python -m levi.drift log --tag T [--tag T ...] --note "..." [--ts ISO]
python -m levi.drift card        # prints SILENT when nothing fires
```

## Suggested instinct specs (for the instincts engine)

- **drift-weekly-card**: every Monday morning, run `weekly_card()`.
  If a CARD fires, surface it once in the briefing and once only —
  never nag. If SILENT, say nothing (no "great job staying aligned!",
  no noise).
- **log-from-harvest**: the growth-loop harvester tags what it sees
  and calls `log_activity()` so the instrument has real data without
  manual logging.
- **drift-feeds-teachback**: a fired card is offered as a teach-back
  prompt ("your time went to novelty — is the goal still right?"),
  linking the two alignment instruments.

## Tests

`tests/test_drift.py` — hermetic, synthetic activity, injected `now`.
Covers: CARD fires on real divergence (with concrete evidence in the
body); SILENT on alignment; SILENT on too-little data; SILENT with no
goals; old activity outside the window ignored; partial-share
below-threshold fires; starved goal without voluminous elsewhere stays
silent; goal redefine/drop; tags required; call-time home resolution.
