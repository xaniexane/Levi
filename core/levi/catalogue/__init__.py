"""Free-agent catalogue — outside providers' agents as a free tier in every creation.

Doctrine (Chauncey, 2026-09-18):

* The catalogue lists agents from OUTSIDE providers and offers them as a
  FREE TIER inside all his creations.
* Free tier = usage-limited, but generous and efficient in features.
* Provider monetization stays intact: past the free tier the user pays
  FULL provider price (Gateway Law commerce clause — outside fees are
  the user's, never subsidized).
* An optional MODERATE ad option lets users earn more free credits.
  Moderate means capped and non-intrusive, by policy constants below.
* Catalogue agents attach to agent teams, combining with his force.

Canon laws embodied:

* Gateway Law — the catalogue LISTS and METERS. It never reaches out
  itself: no network calls, no invocation of outside agents. Actual
  outside contact passes through the gateway (Cybrus). This module
  contains zero socket/http imports, enforced by test.
* Founder-gating law — the catalogue is a public surface: it lists the
  RESTRICTED surface, never the full capability. The founder sees
  everything (``views.catalogue_view``); everyone else sees the gated
  surface only.

Stdlib only, offline-first. All money figures are paper records:
over-quota usage is RECORDED at full provider price as the user's
responsibility — nothing here charges anyone.
"""

from __future__ import annotations

from .billing import BillingBoundary, BillingRecord
from .catalogue import FreeAgentCatalogue, UseResult
from .entries import CatalogueEntry, seed_entries
from .ledger import UsageLedger
from .teams import ForceTeam, TeamSeat
from .views import catalogue_view
from .wallet import CreditWallet

__all__ = [
    "BillingBoundary",
    "BillingRecord",
    "CatalogueEntry",
    "CreditWallet",
    "ForceTeam",
    "FreeAgentCatalogue",
    "TeamSeat",
    "UsageLedger",
    "UseResult",
    "catalogue_view",
    "seed_entries",
]
