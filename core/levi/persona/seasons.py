"""Seasons — temporal modulation of LEVI's personality.

A personality that never drifts with time feels mechanical; one that drifts
arbitrarily feels untrustworthy. ``seasons`` is the middle path: pure,
deterministic functions that modulate a base tone-weight vector by

* **circadian hour** — the time of day bends warmth, brevity, and play
  (dawn is quiet, midday is bright, night is dreamy);
* **season of year** — each quarter leans the voice a little (spring:
  curiosity; summer: momentum; autumn: reflection; winter: restraint);
* **streak** — consecutive days the user has talked to LEVI nudge
  familiarity upward, decaying after a week of silence.

Everything is a pure function of ``(weights, moment)`` — no state, no
side effects, no network. The composition with the persona lattice is
explicit: ``seasonal_weights()`` takes a base dict and returns a new one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional


#: The canonical tone axes. Base weights come from the persona lattice /
#: composition layers; seasons only *bends* them, never invents new ones.
TONES = (
    "warmth",
    "brevity",
    "playfulness",
    "formality",
    "reflection",
    "curiosity",
    "momentum",
    "restraint",
)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _hour_arc(hour: int) -> Dict[str, float]:
    """Multiplicative bends per part of day. Values near 1.0 = no bend."""
    if 5 <= hour < 8:  # dawn — quiet, gentle starts
        return {
            "warmth": 1.08,
            "brevity": 1.12,
            "playfulness": 0.92,
            "formality": 0.98,
            "reflection": 1.06,
            "curiosity": 1.05,
            "momentum": 0.95,
            "restraint": 1.02,
        }
    if 8 <= hour < 12:  # morning — bright, forward
        return {
            "warmth": 1.05,
            "brevity": 1.05,
            "playfulness": 1.02,
            "formality": 1.02,
            "reflection": 0.98,
            "curiosity": 1.08,
            "momentum": 1.10,
            "restraint": 0.98,
        }
    if 12 <= hour < 17:  # afternoon — direct, working
        return {
            "warmth": 1.0,
            "brevity": 1.12,
            "playfulness": 0.98,
            "formality": 1.05,
            "reflection": 0.95,
            "curiosity": 1.0,
            "momentum": 1.08,
            "restraint": 1.0,
        }
    if 17 <= hour < 21:  # dusk — reflective, conversational
        return {
            "warmth": 1.08,
            "brevity": 0.95,
            "playfulness": 1.05,
            "formality": 0.95,
            "reflection": 1.12,
            "curiosity": 1.03,
            "momentum": 0.95,
            "restraint": 1.0,
        }
    if 21 <= hour or hour < 2:  # night — dreamy, unhurried
        return {
            "warmth": 1.05,
            "brevity": 0.88,
            "playfulness": 1.08,
            "formality": 0.90,
            "reflection": 1.12,
            "curiosity": 1.05,
            "momentum": 0.88,
            "restraint": 0.98,
        }
    # 2-5: deep night — restrained, minimal
    return {
        "warmth": 0.98,
        "brevity": 1.15,
        "playfulness": 0.90,
        "formality": 0.95,
        "reflection": 1.08,
        "curiosity": 0.95,
        "momentum": 0.90,
        "restraint": 1.10,
    }


def _season_arc(month: int) -> Dict[str, float]:
    """Multiplicative bends per meteorological season (northern-hemisphere
    naming; the *shape* — a year-long slow cycle — is what matters)."""
    if month in (3, 4, 5):  # spring — curiosity
        return {
            "warmth": 1.03,
            "brevity": 1.0,
            "playfulness": 1.05,
            "formality": 0.98,
            "reflection": 0.98,
            "curiosity": 1.12,
            "momentum": 1.03,
            "restraint": 0.98,
        }
    if month in (6, 7, 8):  # summer — momentum
        return {
            "warmth": 1.05,
            "brevity": 0.98,
            "playfulness": 1.10,
            "formality": 0.95,
            "reflection": 0.95,
            "curiosity": 1.05,
            "momentum": 1.12,
            "restraint": 0.95,
        }
    if month in (9, 10, 11):  # autumn — reflection
        return {
            "warmth": 1.02,
            "brevity": 1.0,
            "playfulness": 1.0,
            "formality": 1.0,
            "reflection": 1.12,
            "curiosity": 1.03,
            "momentum": 0.98,
            "restraint": 1.03,
        }
    # winter — restraint
    return {
        "warmth": 1.0,
        "brevity": 1.05,
        "playfulness": 0.95,
        "formality": 1.03,
        "reflection": 1.08,
        "curiosity": 1.0,
        "momentum": 0.95,
        "restraint": 1.12,
    }


def streak_bend(streak_days: int) -> Dict[str, float]:
    """Familiarity nudge from consecutive days of contact.

    0 days → neutral. Grows to a plateau at 7 days; negative (days of
    silence) decays the nudge instead of punishing it.
    """
    if streak_days <= 0:
        decay = max(0.0, 1.0 + streak_days / 7.0)  # -7 → 0, 0 → 1
        return {
            "warmth": 0.95 + 0.05 * decay,
            "brevity": 1.0,
            "playfulness": 0.95 + 0.05 * decay,
            "formality": 1.0,
            "reflection": 1.0,
            "curiosity": 1.0,
            "momentum": 1.0,
            "restraint": 1.0,
        }
    nudge = min(streak_days, 7) / 7.0
    return {
        "warmth": 1.0 + 0.10 * nudge,
        "brevity": 1.0,
        "playfulness": 1.0 + 0.08 * nudge,
        "formality": 1.0 - 0.08 * nudge,
        "reflection": 1.0,
        "curiosity": 1.0 + 0.05 * nudge,
        "momentum": 1.0,
        "restraint": 1.0,
    }


def seasonal_weights(
    base: Dict[str, float], moment: Optional[datetime] = None, streak_days: int = 0
) -> Dict[str, float]:
    """Apply circadian + seasonal + streak bends to a base tone vector.

    Unknown axes in ``base`` pass through untouched; missing axes are not
    invented. Every value is clamped to [0, 1].
    """
    moment = moment or datetime.now()
    hour_bend = _hour_arc(moment.hour)
    season_bend = _season_arc(moment.month)
    familiarity = streak_bend(streak_days)
    out: Dict[str, float] = {}
    for tone, weight in base.items():
        bend = 1.0
        if tone in hour_bend:
            bend *= hour_bend[tone]
        if tone in season_bend:
            bend *= season_bend[tone]
        if tone in familiarity:
            bend *= familiarity[tone]
        out[tone] = _clamp(weight * bend)
    return out


def describe(moment: Optional[datetime] = None) -> Dict[str, str]:
    """Human-readable read of the current temporal season."""
    moment = moment or datetime.now()
    hour = moment.hour
    part = (
        "dawn"
        if 5 <= hour < 8
        else "morning"
        if 8 <= hour < 12
        else "afternoon"
        if 12 <= hour < 17
        else "dusk"
        if 17 <= hour < 21
        else "night"
        if (21 <= hour or hour < 2)
        else "deep night"
    )
    if moment.month in (3, 4, 5):
        season = "spring"
    elif moment.month in (6, 7, 8):
        season = "summer"
    elif moment.month in (9, 10, 11):
        season = "autumn"
    else:
        season = "winter"
    return {"part_of_day": part, "season": season, "date": moment.date().isoformat()}
