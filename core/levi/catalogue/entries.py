"""Catalogue entries — one per outside provider's agent.

An entry describes the PUBLIC, restricted surface: what a non-founder
user may know (capabilities, free-tier quota, credit cost, full provider
price). The founder-only surface (``full_capabilities`` — the agent's
true potential) is never served to non-founders; see ``views``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CatalogueEntry:
    """One outside provider's agent, listed in the catalogue."""

    id: str  # lowercase slug, unique in the catalogue
    provider: str
    agent_name: str
    blurb: str = ""
    capabilities: List[str] = field(default_factory=list)  # public, gated surface
    full_capabilities: List[str] = field(
        default_factory=list
    )  # founder-only: the true potential
    free_quota: int = 200  # free uses per period — generous by doctrine
    period: str = "monthly"
    credit_cost_per_use: int = 1  # credits per use once free quota is spent
    provider_price_cents_per_use: int = 2  # FULL provider price — never subsidized
    example: bool = False  # True = structural example, not a real provider deal

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise ValueError("entry id must be a non-empty string")
        if self.free_quota < 0:
            raise ValueError("free_quota cannot be negative")
        if self.credit_cost_per_use < 1:
            raise ValueError("credit_cost_per_use must be >= 1")
        if self.provider_price_cents_per_use < 0:
            raise ValueError("provider price cannot be negative")
        self.capabilities = [c for c in (self.capabilities or []) if c and c.strip()]
        self.full_capabilities = [
            c for c in (self.full_capabilities or []) if c and c.strip()
        ]

    def public_dict(self) -> Dict:
        """The gated surface: everything a non-founder may see."""
        return {
            "id": self.id,
            "provider": self.provider,
            "agent_name": self.agent_name,
            "blurb": self.blurb,
            "capabilities": list(self.capabilities),
            "free_quota": self.free_quota,
            "period": self.period,
            "credit_cost_per_use": self.credit_cost_per_use,
            "provider_price_cents_per_use": self.provider_price_cents_per_use,
            "example": self.example,
        }

    def founder_dict(self) -> Dict:
        """Full surface: public dict plus the true potential."""
        d = self.public_dict()
        d["full_capabilities"] = list(self.full_capabilities)
        return d


def seed_entries() -> List[CatalogueEntry]:
    """Representative STRUCTURAL EXAMPLES — not real provider deals.

    Every seed entry carries ``example=True`` and says so in its blurb.
    Real provider onboarding is a business step, not code: a signed deal
    becomes a real entry with ``example=False``.
    """
    return [
        CatalogueEntry(
            id="tidechart",
            provider="Harborlight Systems (example)",
            agent_name="Tidechart (example)",
            blurb="Structural example — not a real provider deal.",
            capabilities=["summarize documents", "extract action items"],
            full_capabilities=[
                "summarize documents",
                "extract action items",
                "cross-document synthesis",
                "priority-ranked briefings",
            ],
            free_quota=300,
            credit_cost_per_use=1,
            provider_price_cents_per_use=2,
            example=True,
        ),
        CatalogueEntry(
            id="ledgerline",
            provider="Bluefield Data (example)",
            agent_name="Ledgerline (example)",
            blurb="Structural example — not a real provider deal.",
            capabilities=["tabulate CSV data", "basic charts"],
            full_capabilities=[
                "tabulate CSV data",
                "basic charts",
                "anomaly detection",
                "scheduled reports",
            ],
            free_quota=200,
            credit_cost_per_use=1,
            provider_price_cents_per_use=3,
            example=True,
        ),
        CatalogueEntry(
            id="wayfinder",
            provider="Copperline Labs (example)",
            agent_name="Wayfinder (example)",
            blurb="Structural example — not a real provider deal.",
            capabilities=["local place lookup", "route sketches"],
            full_capabilities=[
                "local place lookup",
                "route sketches",
                "live traffic fusion",
                "fleet dispatch",
            ],
            free_quota=150,
            credit_cost_per_use=2,
            provider_price_cents_per_use=5,
            example=True,
        ),
        CatalogueEntry(
            id="draftwell",
            provider="Meadowgate AI (example)",
            agent_name="Draftwell (example)",
            blurb="Structural example — not a real provider deal.",
            capabilities=["draft outlines", "tone rewrite"],
            full_capabilities=[
                "draft outlines",
                "tone rewrite",
                "long-form ghostwriting",
                "voice matching",
            ],
            free_quota=250,
            credit_cost_per_use=1,
            provider_price_cents_per_use=2,
            example=True,
        ),
    ]
