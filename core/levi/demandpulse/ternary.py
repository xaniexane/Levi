"""Ternary signal model — the skipped third state.

Competitor demand tools tend to binary alert states: hot / not, trending /
not. The third state they skip is the one that matters most to a buyer:
GATHERING — a signal that is neither quiet nor breaking out, but is
accumulating multi-scan evidence. DemandPulse names it instead of leaving
it invisible.

States:
  dormant    — below the observation floor; nothing to see
  gathering  — above the floor but below the breakout bar, or rising
               without having arrived: the skipped third state
  breakout   — at/above the breakout bar, or spiking >= 3x off a real base

Deterministic, stdlib-only, offline. Every classification is labeled
INFERENCE with a basis note naming the counts it was computed from —
the label law holds here too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

DORMANT = "dormant"
GATHERING = "gathering"
BREAKOUT = "breakout"

STATES = (DORMANT, GATHERING, BREAKOUT)

# Tuning knobs — explicit, documented, adjustable by the owner.
FLOOR = 3  # peak below this over the window: dormant
BREAKOUT_COUNT = 8  # last scan at/above this: breakout
BREAKOUT_MULTIPLE = 3.0  # last >= base * this (base >= floor): breakout


@dataclass(frozen=True)
class TernarySignal:
    subject: str
    state: str  # one of STATES
    label: str  # always "INFERENCE" — computed, not observed
    basis: str  # which counts, which rule fired
    counts: List[int]
    velocity: int  # last count minus prior-window peak

    def to_record(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "state": self.state,
            "label": self.label,
            "basis": self.basis,
            "counts": list(self.counts),
            "velocity": self.velocity,
        }


def _clean_counts(counts: Sequence[int], subject: str) -> List[int]:
    """Coerce per-scan counts to non-negative ints.

    Unconvertible items raise a named ValueError (which scan, which
    value) — never a raw TypeError/ValueError from int().
    """
    clean: List[int] = []
    for i, c in enumerate(counts):
        try:
            v = int(c)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"classify({subject!r}): counts[{i}]={c!r} is not a number"
            ) from exc
        clean.append(max(0, v))
    return clean


def _check_knobs(floor: int, breakout_count: int,
                 breakout_multiple: float) -> None:
    """Owner-tunable knobs still have sane ranges — a zero/negative bar
    would silently reclassify every subject."""
    if floor < 0:
        raise ValueError(f"floor must be >= 0, got {floor!r}")
    if breakout_count < 1:
        raise ValueError(f"breakout_count must be >= 1, got {breakout_count!r}")
    if not breakout_multiple > 0:
        raise ValueError(
            f"breakout_multiple must be > 0, got {breakout_multiple!r}")


def classify(
    subject: str,
    counts: Sequence[int],
    *,
    floor: int = FLOOR,
    breakout_count: int = BREAKOUT_COUNT,
    breakout_multiple: float = BREAKOUT_MULTIPLE,
) -> TernarySignal:
    """Classify a subject's per-scan counts (oldest → newest) into a state.

    Pure function — no I/O, no randomness. Empty history is dormant with
    an explicit basis, never an exception. Garbage counts raise a named
    ValueError; insane tuning knobs do too.
    """
    _check_knobs(floor, breakout_count, breakout_multiple)
    clean = _clean_counts(counts, subject)
    peak = max(clean) if clean else 0
    last = clean[-1] if clean else 0
    prior = clean[:-1]
    prior_peak = max(prior) if prior else 0
    velocity = last - prior_peak

    if not clean:
        state = DORMANT
        basis = "no observations in window — dormant by default"
    elif peak < floor:
        state = DORMANT
        basis = f"peak {peak} < floor {floor} over {len(clean)} scans (counts={clean})"
    elif last >= breakout_count:
        state = BREAKOUT
        basis = f"last scan {last} >= breakout bar {breakout_count} (counts={clean})"
    elif prior_peak >= floor and last >= prior_peak * breakout_multiple:
        state = BREAKOUT
        basis = (
            f"last scan {last} >= {breakout_multiple:g}x prior peak "
            f"{prior_peak} (counts={clean})"
        )
    else:
        state = GATHERING
        basis = (
            f"above floor (peak {peak}) but below breakout bar "
            f"{breakout_count}; velocity {velocity:+d} (counts={clean})"
        )

    return TernarySignal(
        subject=subject,
        state=state,
        label="INFERENCE",
        basis=basis,
        counts=clean,
        velocity=velocity,
    )


def classify_all(
    histories: Dict[str, Sequence[int]] | None,
    **kwargs: Any,
) -> List[TernarySignal]:
    """Classify many subjects; deterministic order (sorted by subject).

    A None mapping classifies as no subjects (empty list) — the same
    never-an-exception philosophy as empty history.
    """
    if histories is None:
        return []
    return [classify(s, histories[s], **kwargs) for s in sorted(histories)]
