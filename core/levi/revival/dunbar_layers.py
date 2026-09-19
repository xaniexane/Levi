"""Dunbar layers — nested hard caps on intimacy tiers.

Studied from: fallen-platforms-evening-20260916, report.md [2. Path].

The mechanism, functionally: relationships sort into nested tiers —
roughly 5 intimate, 15 close, 50 friends, 150 meaningful contacts —
and each tier is a hard cap. The nesting is the discipline: a member
of an inner tier must already belong to every tier outside it, and a
tier overflowing denies new adds at add-time rather than spilling
over silently. Promotion and demotion move people between tiers while
keeping both the caps and the nesting invariant.

This module is a software analog of that pattern: ``DunbarLayers`` with
tier caps (5/15/50/150, customizable), deny-closed ``add_to``,
``promote``/``demote`` that preserve nesting, and ``verify`` to audit
the invariant. Tier sizes are exclusive membership counts.

Honesty: tiers are bucket labels enforced by counters — the module
cannot measure intimacy, only slot occupancy. The default 5/15/50/150
is a borrowed approximation, not a law of nature.
"""

from __future__ import annotations

from typing import Dict, List, Optional

ORIGIN = "levi-revival/dunbar-layers"


class TierDenied(Exception):
    """A tier refused the add: cap hit, or nesting violated."""


class DunbarLayers:
    """Nested intimacy tiers with hard caps, enforced at add-time."""

    DEFAULT_TIERS = (("inner", 5), ("close", 15), ("friends", 50), ("contacts", 150))

    def __init__(self, owner: str, tiers: Optional[List[tuple]] = None) -> None:
        self.owner = owner
        tier_defs = tiers if tiers is not None else list(self.DEFAULT_TIERS)
        if not tier_defs:
            raise ValueError("at least one tier required")
        caps = [c for _, c in tier_defs]
        if any(c < 1 for c in caps):
            raise ValueError("tier caps must be positive")
        if caps != sorted(caps):
            raise ValueError("tier caps must be non-decreasing outward")
        self.tier_names: List[str] = [name for name, _ in tier_defs]
        self.tier_caps: Dict[str, int] = dict(tier_defs)
        self.members: Dict[str, set] = {name: set() for name in self.tier_names}

    # -- deny-closed adds -------------------------------------------------

    def _check_nesting(self, tier: str, person: str) -> None:
        """Inner-tier membership requires membership in all outer tiers."""
        idx = self.tier_names.index(tier)
        missing = [
            t for t in self.tier_names[idx + 1 :] if person not in self.members[t]
        ]
        if missing:
            raise TierDenied(
                f"{person!r} must join outer tier(s) {missing} before {tier!r}"
            )

    def add_to(self, tier: str, person: str) -> bool:
        """Add to a tier: cap and nesting enforced, denied closed."""
        if tier not in self.members:
            raise KeyError(f"unknown tier {tier!r}")
        person = person.strip()
        if not person:
            raise ValueError("person must be non-empty")
        if person in self.members[tier]:
            return False
        self._check_nesting(tier, person)
        if len(self.members[tier]) >= self.tier_caps[tier]:
            raise TierDenied(f"tier {tier!r} is full at {self.tier_caps[tier]}")
        self.members[tier].add(person)
        return True

    def remove_from(self, tier: str, person: str) -> bool:
        """Removing from an outer tier cascades inward — nesting is a law,
        not a suggestion."""
        if tier not in self.members:
            raise KeyError(f"unknown tier {tier!r}")
        if person not in self.members[tier]:
            return False
        idx = self.tier_names.index(tier)
        for inner in self.tier_names[: idx + 1]:
            self.members[inner].discard(person)
        return True

    # -- moving between tiers --------------------------------------------

    def promote(self, person: str, to_tier: str) -> bool:
        """Move one tier inward; nesting and the target cap still apply."""
        idx = self.tier_names.index(to_tier)
        outer = self.tier_names[idx + 1] if idx + 1 < len(self.tier_names) else None
        if outer is not None and person not in self.members[outer]:
            raise TierDenied(
                f"{person!r} is not in outer tier {outer!r}; cannot promote"
            )
        if person in self.members[to_tier]:
            return False
        if len(self.members[to_tier]) >= self.tier_caps[to_tier]:
            raise TierDenied(f"tier {to_tier!r} is full at {self.tier_caps[to_tier]}")
        self.members[to_tier].add(person)
        return True

    def demote(self, person: str, from_tier: str) -> bool:
        """Move one step outward: drop from the named tier only."""
        if from_tier not in self.members:
            raise KeyError(f"unknown tier {from_tier!r}")
        if person not in self.members[from_tier]:
            return False
        self.members[from_tier].discard(person)
        return True

    # -- introspection ----------------------------------------------------

    def tier_of(self, person: str) -> Optional[str]:
        """The innermost tier a person belongs to, or None."""
        for tier in self.tier_names:
            if person in self.members[tier]:
                return tier
        return None

    def tier_size(self, tier: str) -> int:
        return len(self.members[tier])

    def verify(self) -> List[str]:
        """Audit caps and nesting; returns a list of violations (empty =
        healthy)."""
        problems = []
        for tier in self.tier_names:
            if len(self.members[tier]) > self.tier_caps[tier]:
                problems.append(f"tier {tier!r} over cap")
        for i, tier in enumerate(self.tier_names):
            for person in self.members[tier]:
                for outer in self.tier_names[i + 1 :]:
                    if person not in self.members[outer]:
                        problems.append(
                            f"{person!r} in {tier!r} missing from {outer!r}"
                        )
        return problems
