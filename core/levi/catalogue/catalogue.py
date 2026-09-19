"""FreeAgentCatalogue — the facade: entries, metering, wallet, billing, teams.

``use_agent`` is the single metering path for outside-agent usage:

1. founder (per ``levi.cybrus.identity.is_founder``) — unlimited,
   unmetered; the founder never queues behind a gate;
2. inside the entry's free quota — free, counted by the ledger;
3. past quota with credits — credits spent at the entry's per-use cost;
4. past quota without credits — a BillingRecord at FULL provider price,
   stamped as the user's responsibility (paper only; nothing is charged).

The catalogue meters. It never invokes an outside agent and never
touches the network — invocation passes through the gateway (Cybrus).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from levi.cybrus.identity import is_founder

from .billing import BillingBoundary
from .entries import CatalogueEntry, seed_entries
from .ledger import UsageLedger
from .teams import ForceTeam
from .views import catalogue_view
from .wallet import CreditWallet


@dataclass
class UseResult:
    """Outcome of one metered use."""

    ok: bool
    via: str  # "founder" | "free_quota" | "credits" | "provider_billed"
    entry_id: str
    detail: Dict = field(default_factory=dict)


class CatalogueError(Exception):
    """Unknown entry, unknown team, or other catalogue misuse."""


class FreeAgentCatalogue:
    """The free-agent catalogue: list, meter, grant, bill, attach."""

    def __init__(self, entries: Optional[List[CatalogueEntry]] = None) -> None:
        self._entries: Dict[str, CatalogueEntry] = {}
        for entry in entries if entries is not None else seed_entries():
            self.register(entry)
        self.ledger = UsageLedger()
        self.wallets = CreditWallet()
        self.billing = BillingBoundary()
        self._teams: Dict[str, ForceTeam] = {}

    # -- entries ------------------------------------------------------

    def register(self, entry: CatalogueEntry) -> None:
        if entry.id in self._entries:
            raise CatalogueError(f"duplicate catalogue entry {entry.id!r}")
        self._entries[entry.id] = entry

    def entry(self, entry_id: str) -> CatalogueEntry:
        try:
            return self._entries[entry_id]
        except KeyError:
            raise CatalogueError(f"unknown catalogue entry {entry_id!r}") from None

    def entry_ids(self) -> List[str]:
        return sorted(self._entries)

    def list_for(self, identity_record: Optional[Dict] = None) -> List[Dict]:
        """The catalogue as this identity may see it (founder = full)."""
        return catalogue_view(list(self._entries.values()), identity_record)

    # -- metering -----------------------------------------------------

    def use_agent(
        self,
        user_id: str,
        entry_id: str,
        identity_record: Optional[Dict] = None,
    ) -> UseResult:
        """Meter one use of a catalogue agent. Never invokes it."""
        entry = self.entry(entry_id)

        if is_founder(identity_record):
            return UseResult(ok=True, via="founder", entry_id=entry_id)

        metered = self.ledger.record_use(user_id, entry_id, entry.free_quota)
        if metered["within_free_quota"]:
            return UseResult(
                ok=True, via="free_quota", entry_id=entry_id, detail=metered
            )

        if self.wallets.spend(user_id, entry.credit_cost_per_use):
            return UseResult(
                ok=True,
                via="credits",
                entry_id=entry_id,
                detail={
                    "credits_spent": entry.credit_cost_per_use,
                    "balance": self.wallets.balance(user_id),
                },
            )

        record = self.billing.record(
            user_id=user_id,
            entry_id=entry_id,
            provider=entry.provider,
            agent_name=entry.agent_name,
            uses=1,
            unit_price_cents=entry.provider_price_cents_per_use,
        )
        return UseResult(
            ok=True,
            via="provider_billed",
            entry_id=entry_id,
            detail={
                "billing_record": record.to_dict(),
                "note": "full provider price — user responsibility, nothing charged by us",
            },
        )

    # -- teams --------------------------------------------------------

    def team(self, team_id: str, name: str = "") -> ForceTeam:
        """Get or create a force team by id."""
        if team_id not in self._teams:
            self._teams[team_id] = ForceTeam(team_id, name)
        return self._teams[team_id]

    def attach_to_team(self, team_id: str, entry_id: str, role: str = ""):
        """Seat a catalogue agent on a team under a role."""
        team = self.team(team_id)
        return team.attach_catalogue_agent(
            entry_id, role, known_entry_ids=set(self._entries)
        )

    def teams(self) -> List[ForceTeam]:
        return list(self._teams.values())
