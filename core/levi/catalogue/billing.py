"""Provider billing boundary — over-quota usage at full provider price.

Gateway Law commerce clause (Chauncey, 2026-09-18): users MAY use
outside APIs through our agent teams, but the fees they accrue are
THEIRS — full price, no subsidy, never our responsibility.

This module draws that boundary in code: when a use lands past the
free quota and the user has no credits, a BillingRecord is written at
the entry's FULL provider price, stamped as the user's responsibility.
Paper only — nothing here executes a charge, holds a card, or talks to
a provider. Settlement is a business step outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


@dataclass
class BillingRecord:
    """One over-quota use, priced at full provider price, user-responsible."""

    user_id: str
    entry_id: str
    provider: str
    agent_name: str
    uses: int = 1
    unit_price_cents: int = 0
    responsibility: str = "user"  # never us, never subsidized
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_cents(self) -> int:
        return self.uses * self.unit_price_cents

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "entry_id": self.entry_id,
            "provider": self.provider,
            "agent_name": self.agent_name,
            "uses": self.uses,
            "unit_price_cents": self.unit_price_cents,
            "total_cents": self.total_cents,
            "responsibility": self.responsibility,
            "created_utc": self.created_utc,
        }


class BillingBoundary:
    """Paper ledger of user-responsible provider fees. No charges executed."""

    def __init__(self) -> None:
        self._records: List[BillingRecord] = []

    def record(
        self,
        user_id: str,
        entry_id: str,
        provider: str,
        agent_name: str,
        uses: int,
        unit_price_cents: int,
    ) -> BillingRecord:
        rec = BillingRecord(
            user_id=user_id,
            entry_id=entry_id,
            provider=provider,
            agent_name=agent_name,
            uses=uses,
            unit_price_cents=unit_price_cents,
        )
        self._records.append(rec)
        return rec

    def records_for(self, user_id: str) -> List[BillingRecord]:
        return [r for r in self._records if r.user_id == user_id]

    def total_owed_cents(self, user_id: str) -> int:
        return sum(r.total_cents for r in self.records_for(user_id))

    def to_dict(self) -> Dict:
        return {"records": [r.to_dict() for r in self._records]}

    @staticmethod
    def from_dict(raw: Dict) -> "BillingBoundary":
        boundary = BillingBoundary()
        for item in (raw or {}).get("records", []):
            boundary._records.append(
                BillingRecord(
                    user_id=item["user_id"],
                    entry_id=item["entry_id"],
                    provider=item.get("provider", ""),
                    agent_name=item.get("agent_name", ""),
                    uses=int(item.get("uses", 1)),
                    unit_price_cents=int(item.get("unit_price_cents", 0)),
                    responsibility=item.get("responsibility", "user"),
                    created_utc=item.get(
                        "created_utc", datetime.now(timezone.utc).isoformat()
                    ),
                )
            )
        return boundary
