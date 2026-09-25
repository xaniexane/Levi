"""MOOD rate-limit escalation — reversible containment (L6).

A probing session gets slower answers the more wires it trips. The
escalation ladder is local, bounded, and decays: every quiet interval
steps the level back down. The decoy may slow and contain; it may not
ban, destroy, or permanently mark anyone.

Deterministic by construction: the caller passes explicit timestamps, so
the same call sequence always yields the same levels (L8). No wall clock
inside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

__all__ = ["Escalation", "MAX_LEVEL", "STEP_SECONDS"]

#: Seconds the decoy waits before answering at each level.
_STEP_SECONDS = (0.0, 1.0, 3.0, 10.0, 30.0)
MAX_LEVEL = len(_STEP_SECONDS) - 1
STEP_SECONDS = _STEP_SECONDS

#: Quiet seconds after which one level decays away.
DECAY_SECONDS = 300.0


@dataclass
class _Track:
    level: int = 0
    last_at: float = 0.0


class Escalation:
    """Per-session throttle ladder. ``now`` is caller-supplied seconds."""

    def __init__(self) -> None:
        self._tracks: Dict[str, _Track] = {}

    def note_probe(self, session_id: str, now: float) -> int:
        """A wire tripped: step this session up one level. Returns level."""
        track = self._tracks.get(session_id)
        if track is None:
            track = _Track()
            self._tracks[session_id] = track
        self._decay(track, now)
        track.level = min(MAX_LEVEL, track.level + 1)
        track.last_at = now
        return track.level

    def note_quiet(self, session_id: str, now: float) -> int:
        """No trip on this action: apply decay, hold the level. Returns level."""
        track = self._tracks.get(session_id)
        if track is None:
            return 0
        self._decay(track, now)
        track.last_at = now
        return track.level

    def delay_for(self, session_id: str, now: float) -> float:
        """How long the decoy should wait before answering, in seconds."""
        return STEP_SECONDS[self.level(session_id, now)]

    def level(self, session_id: str, now: float) -> int:
        """Current level for a session after decay."""
        track = self._tracks.get(session_id)
        if track is None:
            return 0
        self._decay(track, now)
        return track.level

    @staticmethod
    def _decay(track: _Track, now: float) -> None:
        quiet = now - track.last_at
        if quiet >= DECAY_SECONDS and track.level > 0:
            steps = int(quiet // DECAY_SECONDS)
            track.level = max(0, track.level - steps)
            track.last_at = now
