"""Cuttlefish display — the paradox holder (class CUT, organ hatter).

Real mechanism: male mourning cuttlefish (Sepia plangon) display male
courtship pattern to a female on one side of the body while
simultaneously displaying female-mimic pattern to a rival male on the
other (Brown, Macquarie U., Biology Letters 2012). Two contradictory
messages, live, at once — each true to its audience. Translated: hold
two contradictory plans with independent confidences; act on both until
evidence crosses a resolution threshold. Paradox is a working state.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


class ParadoxHolder:
    """Keeps two contradictory plans alive until evidence decides."""

    def __init__(
        self,
        plan_a: Any,
        plan_b: Any,
        confidence_a: float = 0.5,
        confidence_b: float = 0.5,
        resolve_at: float = 0.85,
    ) -> None:
        assert 0.0 <= confidence_a <= 1.0
        assert 0.0 <= confidence_b <= 1.0
        self.plan_a = plan_a
        self.plan_b = plan_b
        self.confidence_a = confidence_a
        self.confidence_b = confidence_b
        self.resolve_at = resolve_at
        self.resolved: Optional[str] = None

    def observe(self, supports_a: float, supports_b: float) -> None:
        """Fold in evidence (each 0.0-1.0) for the two plans."""
        self.confidence_a = _clamp(self.confidence_a + 0.5 * (supports_a - supports_b))
        self.confidence_b = _clamp(self.confidence_b + 0.5 * (supports_b - supports_a))
        if self.resolved is None:
            if self.confidence_a >= self.resolve_at:
                self.resolved = "A"
            elif self.confidence_b >= self.resolve_at:
                self.resolved = "B"

    def displays(self) -> Dict[str, Tuple[Any, float]]:
        """Both live displays, like both flanks of the cuttlefish."""
        return {
            "flank_a": (self.plan_a, self.confidence_a),
            "flank_b": (self.plan_b, self.confidence_b),
        }

    def act(self) -> Any:
        """Unresolved: return BOTH plans (the paradox). Resolved: winner."""
        if self.resolved == "A":
            return self.plan_a
        if self.resolved == "B":
            return self.plan_b
        return (self.plan_a, self.plan_b)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))
