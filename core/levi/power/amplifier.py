"""Amplifier — boost (short intensity amp) and gain (step-up toward a band).

Two different jobs that novices confuse:

- Booster: temporary. Multiplies the signal while charges last, then gets
  out of the way. For sprints, not for baselines.
- GainStage: structural. Adds a fixed step toward a target band every round
  until the signal sits inside the band, then holds. For climbing, not for
  spiking.

StepAmplifier is the bookkeeping cousin: named fixed steps ("gain" is +70
in L.W.P.'s word-count domain) applied by kind.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .signal import Signal


class Booster:
    """Short intensity amplification. Burns charges; afterwards passes through."""

    def __init__(self, factor: float = 1.5, charges: int = 1) -> None:
        if factor <= 0:
            raise ValueError(f"Booster: factor must be > 0, got {factor!r}")
        if charges < 0:
            raise ValueError(f"Booster: charges must be >= 0, got {charges!r}")
        self.factor = float(factor)
        self.charges = int(charges)

    @property
    def spent(self) -> bool:
        return self.charges <= 0

    def apply(self, signal: Signal) -> Signal:
        if self.spent:
            return signal
        self.charges -= 1
        out = signal.noted(f"boosted x{self.factor:g}")
        out.value = signal.value * self.factor
        return out


class GainStage:
    """Sustained step-up toward a target band. Holds once the band is reached."""

    def __init__(self, band: Tuple[float, float], step: float) -> None:
        lo, hi = band
        if not lo <= hi:
            raise ValueError(f"GainStage: band must have lo <= hi, got {band!r}")
        if step <= 0:
            raise ValueError(f"GainStage: step must be > 0, got {step!r}")
        self.band = (float(lo), float(hi))
        self.step = float(step)

    def in_band(self, signal: Signal) -> bool:
        lo, hi = self.band
        return lo <= signal.value <= hi

    def apply(self, signal: Signal) -> Signal:
        lo, hi = self.band
        if signal.value >= lo:
            return signal  # in or above the band: hold, do not overshoot
        out = signal.noted(f"gain +{self.step:g}")
        out.value = min(signal.value + self.step, hi)
        return out


class StepAmplifier:
    """Named fixed steps applied by kind. Unknown kinds pass through."""

    def __init__(self, steps: Dict[str, float]) -> None:
        self.steps = {str(k): float(v) for k, v in steps.items()}

    def step(self, kind: str) -> float:
        return self.steps.get(kind, 0.0)

    def apply(self, value: float, kind: str) -> float:
        return float(value) + self.step(kind)
