"""Echoverse voyage engine — the fated-outcome core.

Chauncey's design, from his own words:

  ECHOVERSE_KFX2_PRODUCTION.md — "Echoverse = the SFW companion track:
  branching-scenario simulator (taken / not-taken / wild beats), journal,
  earned rapport, recall — exploration and story-driven companionship."
  Phase 3: "simulator.py stages taken / not-taken / wild beats."
  Phase 2: "earned rapport scored from lived beats (kept sessions,
  replayed scenes, kept promises inside the fiction — explicit rubric,
  no flattery)."

  His 2026-09-22 word — "It is a fated outcome: the end is sealed from
  the start, the voyage is the point. Arriving isn't losing."

The loop::

    sealed fated outcome -> beats walked (taken / not-taken / wild)
        -> journal of lived beats -> earned rapport -> arrival

A voyage begins when its fated outcome is sealed — the destined end,
fixed once and immutable. The voyage is then walked beat by beat; each
beat is staged on a branch — taken (the path walked), not-taken (the
path left behind), or wild (the unexpected). Lived beats are recorded
in the journal, and earned rapport is scored from lived beats on an
explicit rubric the owner can read. When the voyage is walked to its
end, the fated outcome arrives. Arriving is the destination, not a
loss.

Struck framing (not his — invented to fill the order, removed here):
"play-to-lose", "doom", "doom clock", "marks", "echo", "checks".
His words are the spec.

Deterministic: beat ids derive from ``sha256(seed:index:branch:text)``,
so the same seed and the same call sequence always produce the same
voyage. No RNG stream, nothing hidden.

Zone law: SFW, stdlib-only, no network, never imports anything from
``levi.plaiground``. Files (save/load) live under a caller-supplied
home and are written mode 0600.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ZONE = "echoverse"
_ZONE_DIRNAME = "echoverse"
_VOYAGE_DIRNAME = "voyages"
_RECORD_MODE = 0o600

#: The three branches a beat can be staged on — his canonical
#: vocabulary from the production plan.
TAKEN = "taken"
NOT_TAKEN = "not-taken"
WILD = "wild"
BRANCHES = (TAKEN, NOT_TAKEN, WILD)

__all__ = [
    "BRANCHES",
    "NOT_TAKEN",
    "TAKEN",
    "WILD",
    "ZONE",
    "Beat",
    "FateArrivedError",
    "FateNotSealedError",
    "FateSealedError",
    "Voyage",
    "load_voyage",
    "voyage_dir",
]


class FateSealedError(Exception):
    """The fated outcome is already sealed; it cannot be changed."""


class FateNotSealedError(Exception):
    """The voyage has no sealed fated outcome yet; seal one first."""


class FateArrivedError(Exception):
    """The fated outcome has arrived; the voyage is complete."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def voyage_dir(home: Path) -> Path:
    """``~/.levi/echoverse/voyages`` under the caller-supplied home."""
    return Path(home) / ".levi" / _ZONE_DIRNAME / _VOYAGE_DIRNAME


def _write_private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, _RECORD_MODE)
    return path


def _beat_id(seed: int, index: int, branch: str, text: str) -> str:
    raw = "%s:%d:%s:%s" % (seed, index, branch, text)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _slug(hero: str, seed: int) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in hero)[:32] or "hero"
    return "%s_%s" % (safe, abs(hash((hero, seed))) % 10**8)


@dataclass
class Beat:
    """One lived beat of the voyage, staged on a branch."""

    id: str
    branch: str
    text: str
    index: int = 0
    walked_at: str = field(default_factory=_utcnow)


def _rapport_for_beat(_beat: Beat) -> int:
    """The explicit rapport rubric, readable by the owner.

    Every lived beat earns one rapport. The journal is the record; the
    score is a plain count — no hidden weights, no flattery.
    """
    return 1


class Voyage:
    """One voyage toward a sealed fated outcome.

    ``hero`` names the traveler, ``beats`` is how many beats the voyage
    holds, ``seed`` makes every beat id deterministic. The fated outcome
    must be sealed via :meth:`seal_fate` before any beat is walked.
    """

    def __init__(self, hero: str, beats: int, seed: int) -> None:
        if not hero:
            raise ValueError("hero must be a non-empty name")
        if beats < 1:
            raise ValueError("beats must be >= 1")
        self.hero = hero
        self.beats = int(beats)
        self.seed = seed
        self._lived: List[Beat] = []
        self._fate_text: Optional[str] = None
        self._sealed = False

    # ------------------------------------------------------------------
    # The fated outcome — sealed once, never changed.
    # ------------------------------------------------------------------

    def seal_fate(self, text: str) -> None:
        """Fix the destined end. Raises :class:`FateSealedError` if sealed."""
        if self._sealed:
            raise FateSealedError("the fated outcome is sealed and cannot change")
        if not text:
            raise ValueError("fate text must be non-empty")
        self._fate_text = text
        self._sealed = True

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def fate(self) -> str:
        if not self._sealed:
            raise FateNotSealedError("seal the fated outcome before reading it")
        assert self._fate_text is not None
        return self._fate_text

    # ------------------------------------------------------------------
    # Beats — walked on taken / not-taken / wild, recorded in the journal.
    # ------------------------------------------------------------------

    def walk_beat(self, branch: str, text: str) -> Beat:
        """Walk one beat on ``branch`` and record it in the journal.

        ``branch`` is one of ``taken`` / ``not-taken`` / ``wild``. When
        the voyage's beats are all walked, the fated outcome has
        arrived — walking further raises :class:`FateArrivedError`.
        """
        if not self._sealed:
            raise FateNotSealedError("seal the fated outcome before walking beats")
        if self.arrived:
            raise FateArrivedError("the fated outcome has arrived; the voyage is done")
        if branch not in BRANCHES:
            raise ValueError("branch must be one of %s" % (", ".join(BRANCHES)))
        if not text or not text.strip():
            raise ValueError("beat text must be non-empty")
        index = len(self._lived)
        beat = Beat(
            id=_beat_id(self.seed, index, branch, text),
            branch=branch,
            text=" ".join(text.split()),
            index=index,
        )
        self._lived.append(beat)
        return beat

    @property
    def journal(self) -> List[Beat]:
        """The lived beats, in the order they were walked."""
        return list(self._lived)

    @property
    def beats_walked(self) -> int:
        return len(self._lived)

    @property
    def branch_counts(self) -> Dict[str, int]:
        counts = {b: 0 for b in BRANCHES}
        for beat in self._lived:
            counts[beat.branch] += 1
        return counts

    # ------------------------------------------------------------------
    # Earned rapport — scored from lived beats, explicit rubric.
    # ------------------------------------------------------------------

    @property
    def rapport(self) -> int:
        """Earned rapport: scored from lived beats, one per beat."""
        return sum(_rapport_for_beat(b) for b in self._lived)

    # ------------------------------------------------------------------
    # Arrival — the destination, not a loss.
    # ------------------------------------------------------------------

    @property
    def arrived(self) -> bool:
        return len(self._lived) >= self.beats

    # ------------------------------------------------------------------
    # Persistence — caller-supplied home, 0600 files.
    # ------------------------------------------------------------------

    def save(self, home: Path) -> Path:
        """Persist the voyage (beats, seal, journal) under home."""
        payload: Dict[str, Any] = {
            "hero": self.hero,
            "beats": self.beats,
            "seed": self.seed,
            "sealed": self._sealed,
            "fate_text": self._fate_text,
            "lived": [
                {
                    "id": b.id,
                    "branch": b.branch,
                    "text": b.text,
                    "index": b.index,
                    "walked_at": b.walked_at,
                }
                for b in self._lived
            ],
        }
        path = voyage_dir(home) / ("%s.json" % _slug(self.hero, self.seed))
        return _write_private(path, json.dumps(payload, indent=2))

    def state(self) -> Dict[str, Any]:
        """Plain summary of where the voyage stands."""
        return {
            "hero": self.hero,
            "beats": self.beats,
            "beats_walked": self.beats_walked,
            "sealed": self._sealed,
            "arrived": self.arrived,
            "rapport": self.rapport,
            "branch_counts": self.branch_counts,
        }


def load_voyage(home: Path, hero: str, seed: int) -> Voyage:
    """Reload a voyage saved with :meth:`Voyage.save`."""
    path = voyage_dir(home) / ("%s.json" % _slug(hero, seed))
    payload = json.loads(path.read_text(encoding="utf-8"))
    voyage = Voyage(payload["hero"], payload["beats"], payload["seed"])
    voyage._sealed = payload["sealed"]
    voyage._fate_text = payload["fate_text"]
    voyage._lived = [
        Beat(
            id=b["id"],
            branch=b["branch"],
            text=b["text"],
            index=b["index"],
            walked_at=b["walked_at"],
        )
        for b in payload["lived"]
    ]
    return voyage
