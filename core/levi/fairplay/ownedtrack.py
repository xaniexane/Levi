"""The owned track: a progression season the clock cannot kill.

The battle pass's sly trade is not the track \u2014 earning things by
playing is honest fun \u2014 it is the calendar: pay for the right to
grind, then watch the season delete what you did not finish. Halo
Infinite (343 Industries, 2021) showed the inversion and the industry
refused to copy it: passes that never expire, free swapping, cosmetics
only, no loot boxes. This module is that inversion as structure.

LAWS (invariants, machine-checked by tests):
1. NO EXPIRY, EVER. There is no deadline field, no season clock, no
   decay. Progress only ever moves forward.
2. FREE SWAPPING. Many tracks may be owned; one is active at a time;
   switching preserves every track's progress exactly.
3. COSMETICS ONLY. A reward that changes power is refused at
   registration. ``kind`` must be in ``COSMETIC_KINDS``.
4. NOTHING VANISHES. Completed tracks, unlocked rewards, and progress
   have no delete path. ``export_state()``/``import_state()`` carry the
   whole shelf across machines.
5. NO TIER-SKIPS, NO TILL. Progress comes from ``add_play()`` alone.

Clean-room from first principles; no game code was read or copied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Reward kinds that cannot change power. Anything else is refused.
COSMETIC_KINDS = (
    "skin",
    "emote",
    "banner",
    "title",
    "avatar",
    "music",
    "spray",
    "charm",
    "frame",
    "pet",  # cosmetic companions: they follow, they never fight
)


@dataclass(frozen=True)
class Reward:
    """One tier's prize. ``kind`` must be cosmetic; ``tier`` starts at 1."""

    tier: int
    name: str
    kind: str

    def __post_init__(self) -> None:
        if self.tier < 1:
            raise ValueError("tiers start at 1")
        if self.kind not in COSMETIC_KINDS:
            raise ValueError(
                f"reward kind {self.kind!r} is not cosmetic \u2014 "
                "power is not for sale here"
            )


class OwnedTrack:
    """One never-expiring progression track."""

    def __init__(self, name: str, rewards: List[Reward], xp_per_tier: int = 100) -> None:
        if xp_per_tier < 1:
            raise ValueError("xp_per_tier must be positive")
        tiers = sorted({r.tier for r in rewards})
        if tiers != list(range(1, len(tiers) + 1)):
            raise ValueError("tiers must be a contiguous run starting at 1")
        self.name = name
        self.rewards = tuple(sorted(rewards, key=lambda r: r.tier))
        self.xp_per_tier = xp_per_tier
        self.xp = 0
        self._claimed: List[str] = []

    @property
    def level(self) -> int:
        return min(self.xp // self.xp_per_tier, len(self.rewards))

    def add_play(self, amount: int) -> int:
        """Progress comes from play and nothing else. Law 5."""
        if amount < 0:
            raise ValueError("play cannot be negative")
        self.xp += amount
        return self.level

    def claimable(self) -> List[Reward]:
        return [
            r for r in self.rewards
            if r.tier <= self.level and r.name not in self._claimed
        ]

    def claim(self) -> List[str]:
        """Claim everything earned so far. Claims are permanent."""
        newly = [r.name for r in self.claimable()]
        self._claimed.extend(newly)
        return newly

    @property
    def claimed(self) -> List[str]:
        return list(self._claimed)

    def export_state(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "xp": self.xp,
            "xp_per_tier": self.xp_per_tier,
            "claimed": list(self._claimed),
            "rewards": [
                {"tier": r.tier, "name": r.name, "kind": r.kind}
                for r in self.rewards
            ],
        }

    @classmethod
    def import_state(cls, state: Dict[str, object]) -> "OwnedTrack":
        track = cls(
            str(state["name"]),
            [Reward(**r) for r in state["rewards"]],  # type: ignore[arg-type]
            xp_per_tier=int(state["xp_per_tier"]),
        )
        track.xp = int(state["xp"])
        track._claimed = list(state["claimed"])  # type: ignore[arg-type]
        return track


class TrackShelf:
    """Owns many tracks; exactly one active at a time. Law 2."""

    def __init__(self) -> None:
        self._tracks: Dict[str, OwnedTrack] = {}
        self._active: Optional[str] = None

    def add(self, track: OwnedTrack) -> None:
        if track.name in self._tracks:
            raise ValueError(f"track {track.name!r} already on the shelf")
        self._tracks[track.name] = track
        if self._active is None:
            self._active = track.name

    @property
    def active(self) -> Optional[OwnedTrack]:
        return self._tracks.get(self._active) if self._active else None

    def switch(self, name: str) -> OwnedTrack:
        """Swap the active track. Progress on every track is untouched."""
        if name not in self._tracks:
            raise KeyError(f"no track named {name!r}")
        self._active = name
        return self._tracks[name]

    def progress_snapshot(self) -> Dict[str, Tuple[int, List[str]]]:
        return {
            name: (t.xp, t.claimed) for name, t in self._tracks.items()
        }
