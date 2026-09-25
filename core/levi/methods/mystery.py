"""The 'Mystery' of the Craft: guild knowledge secrecy.

Origin: apprentices learned only basic techniques until trusted with
the guild's 'mystery' — its trade secrets. Secrecy was enforced by
oath, monopoly law, and economic sanction: expulsion meant losing the
right to practice plus religious burial rites. The secrecy was
load-bearing for the monopoly, not just for quality: once Lyon's
buttonmakers taught girls the trade, the 'mystery' leaked and the
monopoly wobbled.

What it is in LEVI: ``TieredDisclosure`` — knowledge items carry a
tier; a member's tier rises only through demonstrated loyalty
milestones, never by request or seniority alone. Access above a
member's tier is refused. Knowledge partitioning is the mechanism.

Honesty label: LOAD-BEARING — tier gating with milestone-based
promotion is a concrete, transferable mechanism.

Deny-closed inputs: empty member/item names, duplicate member or item
ids, negative tiers, unknown member or item ids, empty milestones,
promoting without enough milestones banked, promoting past the highest
defined tier, and accessing knowledge above the member's tier are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["KnowledgeItem", "TieredDisclosure", "MILESTONES_PER_TIER"]

#: Demonstrated loyalty milestones required to rise one tier.
MILESTONES_PER_TIER = 2


@dataclass
class KnowledgeItem:
    id: str
    title: str
    tier: int

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("knowledge title must be a non-empty string")
        self.title = self.title.strip()
        if not isinstance(self.tier, int) or isinstance(self.tier, bool):
            raise ValueError("tier must be an integer")
        if self.tier < 0:
            raise ValueError("tier must be >= 0")


@dataclass
class _Member:
    id: str
    name: str
    tier: int = 0
    milestones: list[str] = field(default_factory=list)


class TieredDisclosure:
    """Basics first, secrets only after proven loyalty. A member's tier
    is earned milestone by milestone; there is no other way up."""

    def __init__(self):
        self._items: dict[str, KnowledgeItem] = {}
        self._members: dict[str, _Member] = {}
        self._counter = 0

    # -- the partition ---------------------------------------------------------
    def add_knowledge(self, title: str, tier: int) -> KnowledgeItem:
        """File a knowledge item at a disclosure tier."""
        item = KnowledgeItem(id="", title=title, tier=tier)
        if any(i.title.lower() == item.title.lower() for i in self._items.values()):
            raise ValueError(f"duplicate knowledge item: {item.title!r}")
        self._counter += 1
        item.id = f"know-{self._counter}"
        self._items[item.id] = item
        return item

    def register_member(self, name: str) -> str:
        """Admit a member at tier 0: basics only."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("member name must be a non-empty string")
        name = name.strip()
        if any(m.name.lower() == name.lower() for m in self._members.values()):
            raise ValueError(f"duplicate member: {name!r}")
        self._counter += 1
        member_id = f"member-{self._counter}"
        self._members[member_id] = _Member(id=member_id, name=name)
        return member_id

    # -- loyalty, demonstrated ---------------------------------------------------
    def record_milestone(self, member_id: str, milestone: str) -> None:
        """Bank one demonstrated-loyalty milestone for a member."""
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"unknown member: {member_id!r}")
        if not isinstance(milestone, str) or not milestone.strip():
            raise ValueError("milestone must be a non-empty string")
        member.milestones.append(milestone.strip())

    def promote(self, member_id: str) -> int:
        """Raise a member one tier. Requires enough banked milestones;
        there is no promotion by request, seniority, or favor."""
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"unknown member: {member_id!r}")
        max_tier = max((i.tier for i in self._items.values()), default=0)
        if member.tier >= max_tier:
            raise ValueError(
                f"member {member.name!r} already holds the highest tier ({max_tier})"
            )
        if len(member.milestones) < MILESTONES_PER_TIER:
            raise ValueError(
                f"promotion refused: {len(member.milestones)} milestones "
                f"banked, {MILESTONES_PER_TIER} required"
            )
        member.tier += 1
        member.milestones = member.milestones[MILESTONES_PER_TIER:]
        return member.tier

    # -- the gate -----------------------------------------------------------------
    def access(self, member_id: str, item_id: str) -> KnowledgeItem:
        """Read a knowledge item. Above-tier access is refused — the
        partition is the whole point."""
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"unknown member: {member_id!r}")
        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"unknown knowledge item: {item_id!r}")
        if member.tier < item.tier:
            raise ValueError(
                f"access denied: {member.name!r} holds tier {member.tier}, "
                f"{item.title!r} requires tier {item.tier}"
            )
        return item

    def member_tier(self, member_id: str) -> int:
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"unknown member: {member_id!r}")
        return member.tier
