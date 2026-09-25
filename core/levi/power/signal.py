"""Power signal — the unit of energy on a LEVI power rail.

A Signal is deliberately dumb: a magnitude, a strength (how intact it is),
a noise fraction, and an opaque payload. Organs attach meaning; this layer
only moves energy lawfully — it decays with distance, and it can be
converted, amplified, repeated, shared across consumers, and isolated
when faulty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class Signal:
    """One packet of signal energy."""

    value: float = 0.0
    strength: float = 1.0  # 0..1 — how intact the signal is
    noise: float = 0.0  # 0..1 — noise fraction riding the signal
    payload: Any = None  # opaque cargo; the layer never interprets it
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.value = float(self.value)
        self.strength = _clamp(self.strength)
        self.noise = _clamp(self.noise)

    def noted(self, tag: str) -> "Signal":
        """Copy of this signal with an extra tag."""
        return Signal(
            value=self.value,
            strength=self.strength,
            noise=self.noise,
            payload=self.payload,
            tags=[*self.tags, tag],
        )


def attenuate(signal: Signal, factor: float) -> Signal:
    """Decay a signal by one hop: strength falls, value holds, noise creeps."""
    if not 0.0 < factor <= 1.0:
        raise ValueError(f"attenuate: factor must be in (0, 1], got {factor!r}")
    return Signal(
        value=signal.value,
        strength=signal.strength * factor,
        noise=_clamp(signal.noise + (1.0 - factor) * 0.25),
        payload=signal.payload,
        tags=list(signal.tags),
    )


def signal_to_noise(signal: Signal) -> float:
    """Crude SNR: strength per unit noise. Infinite when perfectly clean."""
    if signal.noise <= 0.0:
        return float("inf")
    return signal.strength / signal.noise


def degraded(signal: Signal, floor: float = 0.2) -> bool:
    """True when the signal has decayed below a usable strength floor."""
    return signal.strength < floor
