"""Communities as first-class identity objects.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #10)

The mechanism: an interest group is not a page you follow — it is an
*identity object* with its own name, charter, member roster, and badges.
Members join and leave, founders steward the charter, and a community
can vouch for a member's role (a "belonging badge") that the member
carries as part of their identity.

Honest limit: belonging is attested locally. This module keeps rosters
and badges consistent; it does not authenticate people, moderate content,
or talk to any external service.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


ORIGIN = "levi-revival/community-identity"

ROLE_FOUNDER = "founder"
ROLE_MODERATOR = "moderator"
ROLE_MEMBER = "member"

VALID_ROLES = {ROLE_FOUNDER, ROLE_MODERATOR, ROLE_MEMBER}


@dataclass
class Member:
    """One person's standing inside a community."""

    name: str
    role: str = ROLE_MEMBER
    badges: List[str] = field(default_factory=list)
    joined_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class Community:
    """An interest group that is itself an identity object."""

    name: str
    charter: str
    founder: str
    tags: List[str] = field(default_factory=list)
    members: Dict[str, Member] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        self.charter = (self.charter or "").strip()
        if not self.name:
            raise ValueError("community name must be non-empty")
        if not self.charter:
            raise ValueError("charter must be non-empty")
        if self.founder not in self.members:
            self.members[self.founder] = Member(name=self.founder, role=ROLE_FOUNDER)

    # -- membership -----------------------------------------------------
    def join(self, name: str) -> Member:
        name = _check_name(name)
        if name in self.members:
            raise ValueError(f"already a member: {name!r}")
        member = Member(name=name)
        self.members[name] = member
        return member

    def leave(self, name: str) -> Member:
        member = self._member(name)
        if member.role == ROLE_FOUNDER:
            others = [m for m in self.members if m != name]
            if others:
                raise ValueError("founder must hand off before leaving")
        return self.members.pop(name)

    def hand_off(self, old_founder: str, new_founder: str) -> None:
        """Transfer founder stewardship to another member."""
        old = self._member(old_founder)
        new = self._member(new_founder)
        if old.role != ROLE_FOUNDER:
            raise ValueError(f"{old_founder!r} is not the founder")
        old.role = ROLE_MEMBER
        new.role = ROLE_FOUNDER
        self.founder = new_founder

    def set_role(self, actor: str, target: str, role: str) -> None:
        """Founder (or moderator promoting up to moderator) assigns a role."""
        by = self._member(actor)
        who = self._member(target)
        if role not in VALID_ROLES:
            raise ValueError(f"unknown role: {role!r}")
        if role == ROLE_FOUNDER:
            raise ValueError("use hand_off to transfer founder status")
        if by.role == ROLE_FOUNDER:
            who.role = role
        elif by.role == ROLE_MODERATOR and role == ROLE_MEMBER:
            who.role = role
        else:
            raise PermissionError(f"{actor!r} cannot assign role {role!r}")

    # -- belonging badges -----------------------------------------------
    def award_badge(self, actor: str, target: str, badge: str) -> None:
        """A founder/moderator vouches for a member with a named badge."""
        by = self._member(actor)
        who = self._member(target)
        if by.role not in (ROLE_FOUNDER, ROLE_MODERATOR):
            raise PermissionError("only stewards award badges")
        badge = (badge or "").strip().lower()
        if not badge:
            raise ValueError("badge must be non-empty")
        if badge not in who.badges:
            who.badges.append(badge)

    def revoke_badge(self, actor: str, target: str, badge: str) -> None:
        by = self._member(actor)
        who = self._member(target)
        if by.role not in (ROLE_FOUNDER, ROLE_MODERATOR):
            raise PermissionError("only stewards revoke badges")
        badge = (badge or "").strip().lower()
        if badge in who.badges:
            who.badges.remove(badge)

    # -- reading ----------------------------------------------------------
    def roster(self) -> List[Member]:
        order = {ROLE_FOUNDER: 0, ROLE_MODERATOR: 1, ROLE_MEMBER: 2}
        return sorted(self.members.values(), key=lambda m: (order[m.role], m.name))

    def member_count(self) -> int:
        return len(self.members)

    def identity_card(self, name: str) -> Dict:
        """The portable statement of one person's belonging."""
        member = self._member(name)
        return {
            "community": self.name,
            "member": member.name,
            "role": member.role,
            "badges": list(member.badges),
            "joined_at": member.joined_at,
        }

    def _member(self, name: str) -> Member:
        if name not in self.members:
            raise KeyError(f"not a member: {name!r}")
        return self.members[name]


def _check_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("name must be non-empty")
    return name


def found_community(
    name: str, charter: str, founder: str, tags: Optional[List[str]] = None
) -> Community:
    """Create a new community identity with its charter and founder."""
    return Community(
        name=name, charter=charter, founder=_check_name(founder), tags=list(tags or [])
    )
