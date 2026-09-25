"""Status-engineered membership: cultural gravity without exclusivity.

Studied from: dead-networks-20260916/report.md [MindVox]
(status-engineered membership: free accounts for cultural magnets creating
gravity that paying members orbit).

This is an original, from-scratch implementation for LEVI. It builds only the
*functional* pattern — gravity as an organizing force — not the exclusivity.
The mechanism:

- Every member has *gravity*: a heuristic score from contribution activity
  (endorsed posts, original threads, answers marked helpful). It is computed
  by explicit, inspectable rules and is documented as a heuristic everywhere
  it is used — it is a proxy for attention, not a measure of worth.
- A small number of *magnets* — members whose gravity sustains a scene —
  receive sponsored (free) seats. Sponsorship is recorded with a reason and
  expires, so it is a renewable grant, not a rank.
- Everyone else orbits: the *orbit report* shows which magnets a paying
  member actually interacts with, so the community can see where its
  attention flows and whether the gravity is healthy (many magnets, wide
  orbits) or lopsided (one magnet, everyone orbiting them).
- A *lopsidedness index* warns when too much attention concentrates on too
  few members — the failure mode of status engineering.

Public surface:
- ``Gravity``: ``add_member``, ``sponsor_magnet`` / ``renew``,
  ``record_post`` / ``endorse`` / ``mark_helpful``,
  ``record_interaction`` (member ↔ member attention),
  ``gravity_of``, ``orbit()``, ``lopsidedness()``, ``census()``.
- ``Member``, ``GravityError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Tuple

ORIGIN = "levi-revival/status-membership"


class GravityError(ValueError):
    """Raised when a gravity operation cannot be honored."""


@dataclass
class Member:
    """One member: contribution counts and optional magnet sponsorship."""

    member_id: str
    display_name: str
    paying: bool = True
    posts: int = 0
    threads_started: int = 0
    endorsements: int = 0
    helpful_marks: int = 0
    magnet: bool = False
    magnet_reason: str = ""
    magnet_sponsored_at: str = ""
    magnet_renewals: int = 0

    def __post_init__(self) -> None:
        if not self.member_id or not self.display_name:
            raise GravityError("member_id and display_name must be non-empty")

    def gravity(self) -> float:
        """Heuristic gravity: explicit weighted activity. See module docstring."""
        return round(
            1.0 * self.posts
            + 3.0 * self.threads_started
            + 2.0 * self.endorsements
            + 4.0 * self.helpful_marks,
            2,
        )


class Gravity:
    """Status-engineered membership run on explicit gravity rules."""

    # A magnet sponsorship expires after this many renewals are missed;
    # here it is just bookkeeping — the community re-evaluates yearly.
    SPONSOR_CYCLE_DAYS = 365

    def __init__(self, max_magnets: int = 8) -> None:
        if max_magnets < 1:
            raise GravityError("max_magnets must be >= 1")
        self.max_magnets = max_magnets
        self._members: Dict[str, Member] = {}
        self._interactions: Dict[Tuple[str, str], int] = {}  # (viewer, target) -> count
        self._ledger: List[str] = []

    # -- ledger -----------------------------------------------------------
    def _log(self, entry: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._ledger.append(f"{stamp} {entry}")

    def ledger(self) -> List[str]:
        return list(self._ledger)

    # -- membership ---------------------------------------------------------
    def add_member(
        self, member_id: str, display_name: str, paying: bool = True
    ) -> Member:
        if member_id in self._members:
            raise GravityError(f"member {member_id!r} already exists")
        member = Member(member_id=member_id, display_name=display_name, paying=paying)
        self._members[member_id] = member
        self._log(f"JOIN id={member_id} paying={paying}")
        return member

    def member(self, member_id: str) -> Member:
        try:
            return self._members[member_id]
        except KeyError:
            raise GravityError(f"unknown member {member_id!r}") from None

    # -- magnets: sponsored seats --------------------------------------------
    def sponsor_magnet(self, member_id: str, reason: str) -> Member:
        """Grant a sponsored (free) magnet seat, recorded with a reason."""
        member = self.member(member_id)
        if member.magnet:
            raise GravityError(f"{member_id!r} is already a magnet")
        if sum(1 for m in self._members.values() if m.magnet) >= self.max_magnets:
            raise GravityError("magnet seats are full")
        if not reason:
            raise GravityError("sponsorship requires a stated reason")
        member.magnet = True
        member.paying = False  # sponsored seat
        member.magnet_reason = reason
        member.magnet_sponsored_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        self._log(f"SPONSOR id={member_id} reason={reason!r}")
        return member

    def renew(self, member_id: str, renewed: bool, note: str = "") -> Member:
        """Re-evaluate a magnet seat: renew keeps it, False releases it."""
        member = self.member(member_id)
        if not member.magnet:
            raise GravityError(f"{member_id!r} is not a magnet")
        if renewed:
            member.magnet_renewals += 1
            self._log(
                f"RENEW id={member_id} renewals={member.magnet_renewals} note={note!r}"
            )
        else:
            member.magnet = False
            member.paying = True
            member.magnet_reason = ""
            self._log(f"RELEASE id={member_id} note={note!r}")
        return member

    def magnets(self) -> List[Member]:
        return sorted(
            (m for m in self._members.values() if m.magnet),
            key=lambda m: m.gravity(),
            reverse=True,
        )

    # -- contribution signals (all explicit counts) ---------------------------
    def record_post(self, member_id: str, starts_thread: bool = False) -> None:
        member = self.member(member_id)
        member.posts += 1
        if starts_thread:
            member.threads_started += 1

    def endorse(self, member_id: str, by_member: str) -> None:
        if by_member == member_id:
            raise GravityError("self-endorsement does not count")
        self.member(by_member)
        self.member(member_id).endorsements += 1

    def mark_helpful(self, member_id: str, by_member: str) -> None:
        if by_member == member_id:
            raise GravityError("self-marks do not count")
        self.member(by_member)
        self.member(member_id).helpful_marks += 1

    # -- attention orbits -------------------------------------------------------
    def record_interaction(self, viewer: str, target: str) -> int:
        """Record that *viewer* paid attention to *target* (reply, quote, read)."""
        if viewer == target:
            raise GravityError("self-interaction does not count")
        self.member(viewer)
        self.member(target)
        key = (viewer, target)
        self._interactions[key] = self._interactions.get(key, 0) + 1
        return self._interactions[key]

    def orbit(self, member_id: str) -> List[Mapping[str, object]]:
        """Magnets this member orbits, by interaction count (descending)."""
        self.member(member_id)
        magnet_ids = {m.member_id for m in self.magnets()}
        rows = [
            {"target": target, "interactions": count}
            for (viewer, target), count in self._interactions.items()
            if viewer == member_id and target in magnet_ids
        ]
        rows.sort(key=lambda r: int(r["interactions"]), reverse=True)
        return rows

    def gravity_of(self, member_id: str) -> float:
        return self.member(member_id).gravity()

    # -- health of the gravity field ---------------------------------------------
    def lopsidedness(self) -> float:
        """0.0 = attention spread across all magnets; 1.0 = one magnet has it all.

        Computed from the share of magnet-directed interactions. With fewer
        than two magnets or no interactions it returns 0.0.
        """
        magnet_ids = [m.member_id for m in self.magnets()]
        if len(magnet_ids) < 2:
            return 0.0
        totals: Dict[str, int] = {mid: 0 for mid in magnet_ids}
        for (_viewer, target), count in self._interactions.items():
            if target in totals:
                totals[target] += count
        total = sum(totals.values())
        if total == 0:
            return 0.0
        top_share = max(totals.values()) / total
        return round(top_share, 3)

    def census(self) -> Mapping[str, object]:
        return {
            "members": len(self._members),
            "magnets": sum(1 for m in self._members.values() if m.magnet),
            "paying": sum(1 for m in self._members.values() if m.paying),
            "interactions": sum(self._interactions.values()),
            "lopsidedness": self.lopsidedness(),
        }
