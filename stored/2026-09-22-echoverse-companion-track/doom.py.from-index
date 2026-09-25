"""Echoverse doom engine — play-to-lose narrative mechanics.

KFX2 absorb of the abstract pattern only: reputation-as-feedback-loop,
inevitable doom. Reversed and rebuilt here as an original LEVI-native
composition — never a copy of any external game's names, text, stats,
or mechanics. Working identifiers throughout; final naming is Chauncey's.

The loop::

    deeds (marks) -> echo (reputation) -> checks (shifted by echo) -> doom clock

A hero carries a SEALED doom: a destined end fixed at the start that
cannot be changed mid-run. Deeds are recorded as marks (what the hero
did, with weight). The echo — what the world says about the hero — is
derived from marks and shifts the odds of every check. Every check also
advances the doom clock by exactly one, and the clock never reverses.
The end is unavoidable; the story is shapeable. Winning = a well-earned
doom.

Deterministic: the voyage owns a ``random.Random`` seeded explicitly;
the same seed and the same call sequence always produce the same run.

Zone law: SFW, stdlib-only, no network, never imports anything from
``levi.plaiground``. Files (save/load) live under a caller-supplied
home and are written mode 0600.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Dict, List, Optional

ZONE = "echoverse"
_ZONE_DIRNAME = "echoverse"
_DOOM_DIRNAME = "doom"
_RECORD_MODE = 0o600

#: Echo magnitude that yields the maximum odds shift.
ECHO_SCALE = 10.0
#: Largest odds shift the echo can apply, in either direction.
MAX_SHIFT = 0.25

__all__ = [
    "ECHO_SCALE",
    "MAX_SHIFT",
    "ZONE",
    "CheckResult",
    "DoomArrivedError",
    "DoomNotSealedError",
    "DoomSealedError",
    "Mark",
    "Voyage",
    "doom_dir",
    "load_voyage",
]


class DoomSealedError(Exception):
    """The doom is already sealed; it cannot be changed mid-run."""


class DoomNotSealedError(Exception):
    """The voyage has no sealed doom yet; seal one before running checks."""


class DoomArrivedError(Exception):
    """The doom clock is full; the destined end has arrived."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def doom_dir(home: Path) -> Path:
    """``~/.levi/echoverse/doom`` under the caller-supplied home."""
    return Path(home) / ".levi" / _ZONE_DIRNAME / _DOOM_DIRNAME


def _write_private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, _RECORD_MODE)
    return path


@dataclass
class Mark:
    """A deed: what the hero did, with weight."""

    deed: str
    weight: float
    index: int = 0
    recorded_at: str = field(default_factory=_utcnow)


@dataclass
class CheckResult:
    """The outcome of one check."""

    success: bool
    roll: float
    shift: float
    difficulty: float
    clock: int
    doomed: bool


class Voyage:
    """One hero's run toward a sealed doom.

    ``hero`` names the hero, ``doom_ticks`` is how many checks the doom
    is away, ``seed`` drives the deterministic roll stream. The doom
    must be sealed via :meth:`seal_doom` before any check runs.
    """

    def __init__(self, hero: str, doom_ticks: int, seed: int) -> None:
        if not hero:
            raise ValueError("hero must be a non-empty name")
        if doom_ticks < 1:
            raise ValueError("doom_ticks must be >= 1")
        self.hero = hero
        self.doom_ticks = int(doom_ticks)
        self.seed = seed
        self._rng = Random(seed)
        self._marks: List[Mark] = []
        self._clock = 0
        self._doom_text: Optional[str] = None
        self._sealed = False

    # ------------------------------------------------------------------
    # Doom — sealed once, never changed.
    # ------------------------------------------------------------------

    def seal_doom(self, text: str) -> None:
        """Fix the destined end. Raises :class:`DoomSealedError` if sealed."""
        if self._sealed:
            raise DoomSealedError("the doom is sealed and cannot be changed")
        if not text:
            raise ValueError("doom text must be non-empty")
        self._doom_text = text
        self._sealed = True

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def doom_text(self) -> str:
        if not self._sealed:
            raise DoomNotSealedError("seal a doom before reading it")
        assert self._doom_text is not None
        return self._doom_text

    # ------------------------------------------------------------------
    # Marks and echo — deeds feed reputation.
    # ------------------------------------------------------------------

    def record_mark(self, deed: str, weight: float) -> Mark:
        """Record a deed with its weight; returns the mark."""
        mark = Mark(deed=deed, weight=float(weight), index=len(self._marks))
        self._marks.append(mark)
        return mark

    @property
    def marks(self) -> List[Mark]:
        return list(self._marks)

    @property
    def echo(self) -> float:
        """Reputation: the sum of all mark weights."""
        return sum(m.weight for m in self._marks)

    def _shift(self) -> float:
        raw = self.echo / ECHO_SCALE
        return max(-MAX_SHIFT, min(MAX_SHIFT, raw))

    # ------------------------------------------------------------------
    # Checks — echo shifts the odds; every check advances the clock.
    # ------------------------------------------------------------------

    @property
    def clock(self) -> int:
        return self._clock

    @property
    def doomed(self) -> bool:
        return self._clock >= self.doom_ticks

    def check(
        self, difficulty: float, deed: Optional[str] = None, weight: float = 0.0
    ) -> CheckResult:
        """Attempt something at ``difficulty`` in [0, 1].

        The echo shifts the roll; a deed may be recorded as a mark
        *after* the attempt resolves (the world hears the deed, the
        next check feels it). The doom clock advances by exactly one
        and never reverses. Raises :class:`DoomArrivedError` once the
        doom has arrived.
        """
        if not self._sealed:
            raise DoomNotSealedError("seal a doom before running checks")
        if self.doomed:
            raise DoomArrivedError("the doom has arrived; the run is over")
        if not 0.0 <= difficulty <= 1.0:
            raise ValueError("difficulty must be in [0, 1]")

        shift = self._shift()
        roll = self._rng.random()
        success = (roll + shift) >= difficulty

        if deed is not None:
            self.record_mark(deed, weight)

        self._clock += 1
        return CheckResult(
            success=success,
            roll=roll,
            shift=shift,
            difficulty=difficulty,
            clock=self._clock,
            doomed=self.doomed,
        )

    # ------------------------------------------------------------------
    # Persistence — caller-supplied home, 0600 files.
    # ------------------------------------------------------------------

    def save(self, home: Path) -> Path:
        """Persist the voyage (including the roll stream) under home."""
        payload: Dict[str, Any] = {
            "hero": self.hero,
            "doom_ticks": self.doom_ticks,
            "seed": self.seed,
            "clock": self._clock,
            "sealed": self._sealed,
            "doom_text": self._doom_text,
            "marks": [
                {
                    "deed": m.deed,
                    "weight": m.weight,
                    "index": m.index,
                    "recorded_at": m.recorded_at,
                }
                for m in self._marks
            ],
            "rng_state": self._rng.getstate(),
        }
        # getstate() returns tuples; JSON needs lists.
        payload["rng_state"] = _tuples_to_lists(payload["rng_state"])
        path = doom_dir(home) / ("%s.json" % _slug(self.hero, self.seed))
        return _write_private(path, json.dumps(payload, indent=2))

    def state(self) -> Dict[str, Any]:
        """Plain summary of where the voyage stands."""
        return {
            "hero": self.hero,
            "clock": self._clock,
            "doom_ticks": self.doom_ticks,
            "sealed": self._sealed,
            "doomed": self.doomed,
            "echo": self.echo,
            "marks": len(self._marks),
        }


def _slug(hero: str, seed: int) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in hero)[:32] or "hero"
    return "%s_%s" % (safe, abs(hash((hero, seed))) % 10**8)


def _tuples_to_lists(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_tuples_to_lists(v) for v in value]
    if isinstance(value, list):
        return [_tuples_to_lists(v) for v in value]
    return value


def _lists_to_tuples(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_lists_to_tuples(v) for v in value)
    return value


def load_voyage(home: Path, hero: str, seed: int) -> Voyage:
    """Reload a voyage saved with :meth:`Voyage.save`."""
    path = doom_dir(home) / ("%s.json" % _slug(hero, seed))
    payload = json.loads(path.read_text(encoding="utf-8"))
    voyage = Voyage(payload["hero"], payload["doom_ticks"], payload["seed"])
    voyage._clock = payload["clock"]
    voyage._sealed = payload["sealed"]
    voyage._doom_text = payload["doom_text"]
    voyage._marks = [
        Mark(
            deed=m["deed"],
            weight=m["weight"],
            index=m["index"],
            recorded_at=m["recorded_at"],
        )
        for m in payload["marks"]
    ]
    voyage._rng.setstate(_lists_to_tuples(payload["rng_state"]))
    return voyage
