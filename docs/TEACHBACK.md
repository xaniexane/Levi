# Teach-Back

**LEVI periodically explains back its model of the user's goals; the
user corrects.** An alignment instrument: instead of silently assuming
what you want, LEVI shows its work, you fix it, and the corrections
are logged with timestamps.

## Purpose

Silent assumptions compound into wrong behavior. Teach-back inverts
the loop: LEVI states what it *believes* your goals are, in plain
language, with confidence. You correct the record; confidence moves
honestly (down when corrected — the old model was wrong; up when you
affirm or when evidence corroborates). Nothing else moves confidence.
No vibes.

## API

```python
from levi.teachback import (
    add_statement,
    model,
    render_brief,
    correct,
    affirm,
    note_evidence,
)

add_statement("ship", "Ship the Levi book by year end", confidence=0.7)

print(render_brief())
# Here's what I believe your goals are. Correct me where I'm wrong:
# - [ship] Ship the Levi book by year end
#   confidence: medium (0.70) · evidence: 0 · corrections: 0

correct("ship", "Ship the book — deadline moved to March")
# -> statement updated, confidence 0.70 -> 0.55, correction logged

affirm("ship")  # confidence +0.10 (cap 1.0)
note_evidence("ship", "drafted ch. 3")  # evidence_count+1, +0.05 (cap 0.95)

for s in model():  # current statements + confidence
    print(s["id"], s["statement"], s["confidence"])

# Append-only history per statement — corrections are preserved, never rewritten.
from levi.teachback import TeachbackModel

TeachbackModel().history("ship")
```

### Confidence law (mechanical, honest)

| Event | Move | Bound |
|---|---|---|
| `correct()` | −0.15 | floor 0.05 |
| `affirm()` | +0.10 | cap 1.0 |
| `note_evidence()` | +0.05 | cap 0.95 — evidence alone never certifies |

A correction *replaces* the statement text and humbles confidence;
the history entry keeps the old wording with a timestamp. Unknown IDs
raise `KeyError`; empty statement text raises `ValueError`.

Data: `<LEVI_HOME>/teachback/goal_model.json` — local JSON only. Home
resolves at call time (`LEVI_HOME` env → `~/.levi`).

## CLI

```
python -m levi.teachback add ID --statement "..." [--confidence 0.5]
python -m levi.teachback show
python -m levi.teachback brief
python -m levi.teachback correct ID --correction "..."
python -m levi.teachback affirm ID
python -m levi.teachback evidence ID --note "..."
```

## Suggested instinct specs (for the instincts engine)

- **teachback-onboarding**: after the first few conversations, `add`
  initial goal-model statements at modest confidence (≤ 0.5) and render
  the brief. Never present a guess as fact.
- **teachback-periodic**: monthly (or when a drift card fires), render
  the brief unprompted and invite corrections — one tap to correct,
  affirm, or drop.
- **teachback-from-growth**: the growth loop's consolidate step may
  propose new statements via `add_statement` at low confidence; the
  user promotes or corrects them.
- **teachback-before-big-decisions**: before a consequential plan,
  re-read the model and confirm the relevant statement is still true.

## Tests

`tests/test_teachback.py` — hermetic, tmp LEVI_HOME. Covers:
correction updates the model; confidence moves in the right direction
(down on correct, up on affirm/evidence); floor/cap bounds; evidence
never reaches certainty; history preserved with old/new wording;
unknown IDs raise; empty model renders an honest brief; history
survives reload; call-time home resolution.
