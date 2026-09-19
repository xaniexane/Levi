"""Transformer — convert energy, isolate noise.

A transformer converts a signal's value from one domain to another
(units, scale, encoding — the caller's function decides) and quarantines
anything too weak to trust. Conversion and noise isolation always travel
together: a transformer never passes rot downstream just because the math
worked.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .signal import Signal

ConvertFn = Callable[[float], float]


class Transformer:
    """One conversion stage with a noise floor."""

    def __init__(
        self,
        convert: Optional[ConvertFn] = None,
        noise_floor: float = 0.0,
        name: str = "transformer",
    ) -> None:
        if not 0.0 <= noise_floor <= 1.0:
            raise ValueError(
                f"Transformer: noise_floor must be in [0, 1], got {noise_floor!r}"
            )
        self._convert = convert
        self.noise_floor = noise_floor
        self.name = name
        self.quarantined: List[Signal] = []
        self.converted = 0

    def convert(self, signal: Signal) -> Optional[Signal]:
        """Convert one signal. Returns None when the result is quarantined."""
        value = (
            self._convert(signal.value) if self._convert is not None else signal.value
        )
        out = signal.noted(self.name)
        out.value = float(value)
        if out.strength < self.noise_floor:
            self.quarantined.append(out)
            return None
        self.converted += 1
        return out

    def chain(self, other: "Transformer") -> "TransformChain":
        """Compose this transformer with another, left to right."""
        return TransformChain([self, other])


class TransformChain:
    """Ordered transformer stages. Stops at the first quarantine."""

    def __init__(self, stages: List[Transformer]) -> None:
        if not stages:
            raise ValueError("TransformChain needs at least one stage")
        self.stages = list(stages)

    def convert(self, signal: Signal) -> Tuple[Optional[Signal], List[str]]:
        """Run the chain. Returns (signal-or-None, stage names that ran)."""
        ran: List[str] = []
        cur: Optional[Signal] = signal
        for stage in self.stages:
            ran.append(stage.name)
            cur = stage.convert(cur)  # type: ignore[arg-type]
            if cur is None:
                return None, ran
        return cur, ran

    @property
    def quarantined(self) -> List[Signal]:
        out: List[Signal] = []
        for stage in self.stages:
            out.extend(stage.quarantined)
        return out
