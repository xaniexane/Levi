"""Season engine — the work/rest rhythm of the keeper.

LEVI never stops, but the keeper is human: rest is load-bearing. The
season engine reads the last 14 days of activity and names the current
season — *surge*, *steady*, or *rest* — with a concrete next-rest
window. Advisory only; it names the weather, it never grounds the
plane.

Inputs
------
``daily_loads``: list of 14 non-negative numbers, events per day,
    oldest first (required; shorter lists are left-padded with zeros)
``rest_target_days``: quiet days wanted per 14-day window
    (default 2, must be >= 1)
``surge_threshold``: average daily load that counts as a surge
    (default 6.0)

The verdict
-----------
- ``rest``   — the stretch ran hot and rest fell short: take rest soon
- ``surge``  — load is high but rest kept pace: surge window is open
- ``steady`` — neither strain nor slack: keep the current pace

A quiet day is any day with zero events. ``next_rest_due_days`` counts
down how soon rest is due (0 means now). Deterministic: same loads,
same season.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_WINDOW = 14


def _loads(raw: Any) -> List[float]:
    if not isinstance(raw, list):
        raise EngineInputError("season: 'daily_loads' must be a list of numbers")
    if len(raw) > _WINDOW:
        raise EngineInputError(f"season: 'daily_loads' covers at most {_WINDOW} days")
    cleaned: List[float] = []
    for i, v in enumerate(raw):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise EngineInputError(f"season: 'daily_loads'[{i}] must be a number")
        if v < 0:
            raise EngineInputError(f"season: 'daily_loads'[{i}] must be >= 0")
        cleaned.append(float(v))
    return [0.0] * (_WINDOW - len(cleaned)) + cleaned


def _season(inputs: Dict[str, Any]) -> EngineResult:
    loads = _loads(inputs.get("daily_loads"))
    rest_target = inputs.get("rest_target_days", 2)
    surge_threshold = inputs.get("surge_threshold", 6.0)
    if isinstance(rest_target, bool) or not isinstance(rest_target, (int, float)):
        raise EngineInputError("season: 'rest_target_days' must be a number")
    if rest_target < 1:
        raise EngineInputError("season: 'rest_target_days' must be >= 1")
    if (
        isinstance(surge_threshold, bool)
        or not isinstance(surge_threshold, (int, float))
        or surge_threshold <= 0
    ):
        raise EngineInputError("season: 'surge_threshold' must be a positive number")

    trace: List[str] = [f"window: {_WINDOW} days, loads: {loads}"]
    avg = sum(loads) / _WINDOW
    peak = max(loads)
    rest_days = sum(1 for v in loads if v == 0)
    rest_met = rest_days >= rest_target
    trace.append(
        f"avg {avg:.2f}/day, peak {peak:g}, quiet days {rest_days} "
        f"(target {rest_target:g}) -> rest {'kept' if rest_met else 'short'}"
    )

    if not rest_met and avg >= 3.0:
        season_word = "rest"
        note = (
            "the stretch ran hot and rest fell short — "
            "take a quiet day before the next surge"
        )
    elif avg >= surge_threshold and rest_met:
        season_word = "surge"
        note = "load is high and rest kept pace — the surge window is open"
    else:
        season_word = "steady"
        note = "neither strain nor slack — hold the current pace"

    next_rest_due = max(int(rest_target - rest_days), 0)
    confidence = round(0.55 + 0.35 * min(avg / max(surge_threshold, 1e-9), 1.0), 3)
    trace.append(f"season '{season_word}' ({note}); rest due in {next_rest_due}d")

    verdict: Dict[str, Any] = {
        "season": season_word,
        "avg_daily_load": round(avg, 2),
        "peak_daily_load": peak,
        "quiet_days": rest_days,
        "rest_target_days": rest_target,
        "rest_kept": rest_met,
        "next_rest_due_days": next_rest_due,
        "note": note,
    }
    return EngineResult(
        engine_id="season", verdict=verdict, confidence=confidence, trace=trace
    )


SEASON_ENGINE = Engine(
    id="season",
    name="Season",
    description=(
        "Work/rest rhythm over the last 14 days of activity: names the "
        "season (surge / steady / rest) and counts down the next rest due."
    ),
    required=("daily_loads",),
    schema={
        "daily_loads": "list of <=14 non-negative daily event counts, oldest first",
        "rest_target_days": "quiet days wanted per window (default 2)",
        "surge_threshold": "avg daily load that counts as surge (default 6.0)",
    },
    risk="info",
    handler=_season,
)

registry.register(SEASON_ENGINE)
