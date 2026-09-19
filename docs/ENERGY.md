# ENERGY — energy-aware scheduling

**Purpose.** Learn the user's real peak hours from when deep work
actually *ships*, then recommend time windows for hard tasks. Not a
productivity gamification layer: a quiet, honest model of when this
particular human does their best work, built from their own evidence.

**Why it exists.** Schedules are usually built on vibes ("I'm a
morning person") or on someone else's routine. ENERGY replaces the
vibe with a ledger: log sessions, mark which ones shipped, and let
the shipped deep sessions teach the model where the peaks are.

## Honesty contract

- `peak_hours()` **refuses to claim peaks under 8 shipped deep
  sessions** (configurable). Below that it returns
  `enough_data: False` and says exactly how many sessions are still
  needed. A peak you haven't earned is not reported.
- Only *shipped* deep sessions teach the model. Time at a desk is not
  evidence of a peak; shipped outcomes are.
- Every `suggest_slot()` recommendation carries a `basis` field:
  `"learned"` (from real session data) or `"heuristic"` (a stated
  fallback). Heuristics are never dressed up as learned.
- Hours are the user's **local** hours. Sessions are recorded in
  local time on purpose — converting to UTC would silently relocate
  a 9am peak.
- Advisory only: it recommends windows. It never books, blocks, or
  reschedules anything.

## API

```python
from levi.energy.tracker import EnergyLog

log = EnergyLog()  # $LEVI_HOME/energy/sessions.json (else ~/.levi)

# Log a session. shipped = did it produce its outcome?
s = log.log_session("2026-09-15T09:00", "2026-09-15T11:30", kind="deep", shipped=True)
# kind is free-form ("deep", "admin", ...); only "deep" feeds peaks.

log.sessions(kind="deep", shipped=True)  # filter the ledger

peaks = log.peak_hours()  # or peak_hours(min_sessions=8,
#              window_hours=3)
# {"enough_data": True, "n_deep_shipped": 12,
#  "windows": [{"start_hour": 9, "end_hour": 12, "minutes": 540.0,
#               "share": 0.88, "rank": 1}, ...]}

slot = log.suggest_slot("hard")  # "hard"|"deep"|"normal"|"admin"|"light"
# {"task_weight": "hard", "when": "2026-09-16T09:00",
#  "until": "2026-09-16T10:00", "window": {...},
#  "basis": "learned",
#  "rationale": "peak window 09:00-12:00 from 12 shipped deep sessions ..."}

slot = log.suggest_slot("deep", now="2026-09-15T07:00")  # injectable now
```

`log_session` rejects non-positive spans and bad datetimes with
`ValueError`. Peak windows are sliding 3-hour windows over the
24-hour cycle, ranked by shipped deep minutes; ties prefer the window
that *starts* on the energy.

## CLI

```bash
python -m levi.energy log --start 2026-09-15T09:00 --end 2026-09-15T11:30 \
    --kind deep --shipped yes
python -m levi.energy peaks [--min-sessions 8]
python -m levi.energy suggest --weight hard [--at 2026-09-15T07:00] [--minutes 90]
python -m levi.energy list [--last 20]
```

## Suggested instinct specs

For the instincts engine (`core/levi/signals/instincts.py`). Evidence
keys are proposed; the engine evaluates them, never vibes.

```yaml
# Once the model has earned its first peak claim, surface it weekly.
- id: instinct.energy_peaks_earned
  fires_on: energy.deep_shipped>=8
  cooldown: 604800        # weekly
  max_grade: NOTE
  does: print learned peak windows; suggest tomorrow's peak slot for the hardest task

# Daily: if peaks are learned, offer today's remaining peak window for deep work.
- id: instinct.energy_today
  fires_on: energy.has_peaks==true
  cooldown: 86400         # daily
  max_grade: NOTE
  does: suggest_slot("hard") for the remainder of today; label basis honestly
```

**Storage:** `$LEVI_HOME/energy/sessions.json` (else `~/.levi`).
Resolved at call time, never at import — tests redirect freely.
**Deps:** stdlib only.
