"""Franklin's moral-perfection ledger: a single-active-target behavior grid.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #17)

The mechanism: pick a small set of behaviors worth cultivating (the
studied form used 13), track them on a day x behavior grid, but keep
only ONE behavior in active focus at a time, rotating the focus in a
fixed order. Each week ends with a review that reports progress per
behavior, so attention stays narrow while the ledger stays wide.

That is the whole insight: willpower doesn't scale, so focus rotates —
but every fault still gets its column, so nothing hides.

stdlib-only. No network. LEVI-native: the ledger is data (plain dicts),
the rotation is a pure function of the day count, and the review is
just arithmetic. Honest framing only — this is behavior logging with a
good UI, not a validated path to virtue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple


ORIGIN = "levi-revival/franklin"

# A canonical 13-slot track list. These are the classic "virtues" slots
# repurposed as neutral behavior slots: the module doesn't preach, it
# tracks. Users can supply their own labels via ``Ledger(behaviors=[...])``.
DEFAULT_BEHAVIORS: Tuple[str, ...] = (
    "temperance",
    "silence",
    "order",
    "resolution",
    "frugality",
    "industry",
    "sincerity",
    "justice",
    "moderation",
    "cleanliness",
    "tranquility",
    "chastity",
    "humility",
)

FOCUS_PERIOD_DAYS = 7


@dataclass
class Ledger:
    """The day x behavior grid.

    ``marks`` maps ``(date_iso, behavior_index)`` -> number of faults
    logged that day (0 means clean). A behavior index is only meaningful
    through ``Ledger.behaviors``.
    """

    behaviors: Sequence[str] = DEFAULT_BEHAVIORS
    marks: Dict[Tuple[str, int], int] = field(default_factory=dict)
    focus_started: str = ""

    def __post_init__(self) -> None:
        if len(self.behaviors) == 0:
            raise ValueError("at least one behavior is required")
        if self.focus_started:
            date.fromisoformat(self.focus_started)  # validate

    # ------------------------------------------------------------------
    # Focus rotation: exactly one active target at a time
    # ------------------------------------------------------------------
    def focus_on(self, today: Optional[str] = None) -> Tuple[str, int]:
        """Return ``(behavior_label, behavior_index)`` in focus *today*.

        Focus rotates through the behavior list in order, one full
        ``FOCUS_PERIOD_DAYS`` week per behavior. Rotation is a pure
        function of the elapsed days since ``focus_started``; before a
        start date is set, the focus is behavior 0.
        """
        idx = self._focus_index(today)
        return self.behaviors[idx], idx

    def _focus_index(self, today: Optional[str] = None) -> int:
        if not self.focus_started:
            return 0
        current = date.fromisoformat(today) if today else date.today()
        start = date.fromisoformat(self.focus_started)
        elapsed = max(0, (current - start).days)
        return (elapsed // FOCUS_PERIOD_DAYS) % len(self.behaviors)

    # ------------------------------------------------------------------
    # Daily marks
    # ------------------------------------------------------------------
    def mark(self, day: str, behavior: int | str, faults: int = 1) -> None:
        """Record ``faults`` against a behavior on ``day`` (ISO date).

        ``behavior`` may be a label or an index. ``faults`` must be
        non-negative; a day with no mark at all counts as clean for the
        weekly review (absence of a mark is data too).
        """
        idx = self._resolve(behavior)
        date.fromisoformat(day)  # validate
        if not isinstance(faults, int) or faults < 0:
            raise ValueError("faults must be a non-negative int")
        self.marks[(day, idx)] = faults

    def faults(self, day: str, behavior: int | str) -> int:
        return self.marks.get((day, self._resolve(behavior)), 0)

    def _resolve(self, behavior: int | str) -> int:
        if isinstance(behavior, int):
            if 0 <= behavior < len(self.behaviors):
                return behavior
            raise ValueError(f"behavior index out of range: {behavior}")
        try:
            return list(self.behaviors).index(behavior)
        except ValueError:
            raise ValueError(f"unknown behavior: {behavior!r}") from None

    # ------------------------------------------------------------------
    # Weekly review
    # ------------------------------------------------------------------
    def weekly_review(
        self, week_start: str, today: Optional[str] = None
    ) -> Dict[str, object]:
        """Compute progress per behavior for the 7 days from ``week_start``.

        Returns a dict with: the week window, which behavior was in focus,
        per-behavior totals (faults + clean days), and the best and worst
        performers. The focus behavior gets its fault count called out
        separately — the review is about the *focus*, not the whole grid.
        """
        start = date.fromisoformat(week_start)
        days = [
            (start + timedelta(days=delta)).isoformat()
            for delta in range(FOCUS_PERIOD_DAYS)
        ]
        per_behavior: List[Dict[str, object]] = []
        for idx, label in enumerate(self.behaviors):
            total = sum(self.marks.get((d, idx), 0) for d in days)
            clean = sum(1 for d in days if self.marks.get((d, idx), 0) == 0)
            per_behavior.append(
                {"behavior": label, "faults": total, "clean_days": clean}
            )
        focus_label, focus_idx = self.focus_on(days[0])
        focus_row = per_behavior[focus_idx]
        by_faults = sorted(per_behavior, key=lambda r: r["faults"])
        return {
            "week_start": days[0],
            "week_end": days[-1],
            "focus": focus_label,
            "focus_faults": focus_row["faults"],
            "focus_clean_days": focus_row["clean_days"],
            "per_behavior": per_behavior,
            "best": by_faults[0]["behavior"],
            "worst": by_faults[-1]["behavior"],
            "total_faults": sum(r["faults"] for r in per_behavior),
        }
