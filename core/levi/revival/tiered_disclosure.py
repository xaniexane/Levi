"""Tiered disclosure with maker/assayer accountability — the honest counterpart.

Studied from: lost-crafts-20260916/report.md [Batch 1] ("Mystery": guild
trade secrecy used to protect rents; the Lyon lesson — female silk artisans
broke the monopoly anyway).

This is an original, from-scratch implementation for LEVI, and it deliberately
does NOT implement secrecy-for-rents. The honest mechanism kept here is
*accountable tiered disclosure*: knowledge items carry a disclosure tier
(public → craft → guild → restricted), access grants are explicit, and every
access is logged on a public accountability ledger naming the maker and the
auditor. The Lyon lesson is encoded as policy: any tier restriction can be
*challenged* — a challenge with a stated public-interest reason is decided by
an independent auditor, and sustained challenges disclose the item at a lower
tier. Secrecy exists only to protect safety/privacy, never rents, and every
restriction expires or is reviewed.

Public surface:
- ``KnowledgeCommons``: ``deposit(item, tier, maker)``,
  ``grant(item_id, party, tier)``, ``read(item_id, party)``,
  ``challenge(item_id, challenger, reason)``, ``rule(item_id, auditor, verdict)``,
  ``ledger()``.
- Tiers: ``Tier.PUBLIC < Tier.CRAFT < Tier.GUILD < Tier.RESTRICTED``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional, Set

ORIGIN = "levi-revival/tiered-disclosure"


class DisclosureError(ValueError):
    """Raised when a disclosure rule cannot be honored."""


class Tier(IntEnum):
    PUBLIC = 0
    CRAFT = 1
    GUILD = 2
    RESTRICTED = 3

    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Item:
    item_id: int
    title: str
    body: str
    tier: Tier
    maker: str
    challenged: bool = False


@dataclass(frozen=True)
class LedgerEntry:
    stamp: str
    actor: str
    action: str
    item_id: int
    detail: str


class KnowledgeCommons:
    """A commons with accountable, challengeable tiered disclosure."""

    def __init__(self, auditors: Optional[Set[str]] = None) -> None:
        self._auditors: Set[str] = set(auditors) if auditors else set()
        self._items: Dict[int, Item] = {}
        self._grants: Dict[int, Dict[str, Tier]] = {}
        self._next_id = 1
        self._ledger: List[LedgerEntry] = []

    # -- ledger -----------------------------------------------------------
    def _log(self, actor: str, action: str, item_id: int, detail: str) -> None:
        self._ledger.append(
            LedgerEntry(
                stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                actor=actor,
                action=action,
                item_id=item_id,
                detail=detail,
            )
        )

    def ledger(self) -> List[LedgerEntry]:
        """The public accountability ledger: who saw / restricted what."""
        return list(self._ledger)

    # -- deposit & grants ---------------------------------------------------
    def deposit(self, title: str, body: str, tier: Tier, maker: str) -> Item:
        if not title or not maker:
            raise DisclosureError("title and maker are required")
        item = Item(
            item_id=self._next_id, title=title, body=body, tier=tier, maker=maker
        )
        self._next_id += 1
        self._items[item.item_id] = item
        self._grants[item.item_id] = {}
        self._log(maker, "deposit", item.item_id, f"tier={tier.label()}")
        return item

    def grant(self, item_id: int, party: str, tier: Tier, granter: str) -> None:
        """Grant a party read access at a tier; logged with granter + maker."""
        item = self._require(item_id)
        if tier < item.tier:
            raise DisclosureError(
                f"cannot grant {party!r} tier {tier.label()} below item tier {item.tier.label()}"
            )
        self._grants[item_id][party] = tier
        self._log(
            granter,
            "grant",
            item_id,
            f"party={party} tier={tier.label()} maker={item.maker}",
        )

    def _tier_of(self, item_id: int, party: str) -> Tier:
        item = self._items[item_id]
        if party == item.maker:
            return Tier.RESTRICTED  # makers always see their own work
        return self._grants[item_id].get(party, Tier.PUBLIC)

    def read(self, item_id: int, party: str) -> str:
        """Read the body if the party's tier covers the item's tier."""
        item = self._require(item_id)
        if self._tier_of(item_id, party) < item.tier:
            self._log(party, "deny", item_id, f"tier={item.tier.label()}")
            raise DisclosureError(
                f"{party!r} lacks tier {item.tier.label()} for item {item_id}"
            )
        self._log(party, "read", item_id, f"maker={item.maker}")
        return item.body

    # -- Lyon lesson: challenges -------------------------------------------
    def challenge(self, item_id: int, challenger: str, reason: str) -> Item:
        """Challenge a tier restriction; marks the item for auditor review."""
        item = self._require(item_id)
        if item.tier == Tier.PUBLIC:
            raise DisclosureError("public items cannot be challenged")
        if not reason.strip():
            raise DisclosureError("a challenge needs a stated public-interest reason")
        self._items[item_id] = Item(
            item_id=item.item_id,
            title=item.title,
            body=item.body,
            tier=item.tier,
            maker=item.maker,
            challenged=True,
        )
        self._log(challenger, "challenge", item_id, f"reason={reason.strip()}")
        return self._items[item_id]

    def rule(self, item_id: int, auditor: str, lower_to: Tier, rationale: str) -> Item:
        """An independent auditor rules on a challenge; sustained challenges
        lower the disclosure tier. Logged publicly."""
        item = self._require(item_id)
        if auditor not in self._auditors:
            raise DisclosureError(f"{auditor!r} is not an independent auditor")
        if not item.challenged:
            raise DisclosureError(f"item {item_id} has no open challenge")
        if lower_to >= item.tier:
            raise DisclosureError("a ruling must lower the tier to disclose more")
        if auditor == item.maker:
            raise DisclosureError("the maker cannot rule on their own item")
        new_item = Item(
            item_id=item.item_id,
            title=item.title,
            body=item.body,
            tier=lower_to,
            maker=item.maker,
            challenged=False,
        )
        self._items[item_id] = new_item
        self._log(
            auditor,
            "rule",
            item_id,
            f"{item.tier.label()} -> {lower_to.label()} rationale={rationale.strip()}",
        )
        return new_item

    def tier_of(self, item_id: int) -> Tier:
        return self._require(item_id).tier

    def _require(self, item_id: int) -> Item:
        item = self._items.get(item_id)
        if item is None:
            raise DisclosureError(f"no item {item_id}")
        return item
