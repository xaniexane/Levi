"""LEVI Dispatch — the local dispatch board (KFX2 workstream DISPATCH, phase 1).

Phase 1 milestone ("The Board"): loads, drivers, and trucks as entities
in a local SQLite ledger; the status lifecycle
booked -> dispatched -> picked_up -> in_transit -> delivered -> invoiced;
a weekly board view; every mutation countersigned by the verifier twin
with an honest receipt.

Local-first: the ledger file lives on the dispatcher's own machine and
nothing here touches the network. There is no seat-, vehicle-, or
insight-based metering anywhere in this package — the 50th driver's
marginal cost is zero by construction.

Hard boundaries (drawn in code, not just docs):
- This package is NOT an ELD and makes NO FMCSA/DOT compliance claim.
  :data:`ELD_DISCLAIMER` is the single source of that truth.
- No model ever fills in a legal document here; paperwork templates are
  a later phase and will be deterministic.
- LEVI advises; the dispatcher decides. Nothing here dispatches a load
  on its own — every transition is an explicit twin-pair call.
"""

from __future__ import annotations

from . import board as board
from . import checkcalls as checkcalls
from . import ledger as ledger
from . import lifecycle as lifecycle
from . import ops_server as ops_server
from . import receipts as receipts
from . import routes as routes
from . import twins as twins
from .board import board_conflicts, render_board_text, week_board, week_dates
from .ledger import (
    DispatchLedger,
    Driver,
    Load,
    Truck,
    default_db_path,
    new_id,
)
from .lifecycle import (
    LoadStatus,
    OfferState,
    Readiness,
    ScheduleFit,
    allowed_next,
    compute_readiness,
    is_terminal,
)
from .receipts import GENESIS_HASH, Receipt, verify_chain
from .routes import (
    FuelParams,
    RankedRoute,
    RoadNetwork,
    RouteError,
    SyntheticRoadNetwork,
    rank_routes,
)
from .checkcalls import (
    Channel,
    ChannelReceipt,
    CheckCallEngine,
    CheckCallRefusal,
    DetentionPolicy,
    SimulatedChannel,
)
from .ops_server import OpsAuth, OpsAuthError, OpsError, OpsServer
from .twins import (
    TIGHT_BUFFER_DAYS,
    DispatcherTwin,
    DispatchRefusal,
    VerifierTwin,
)

__all__ = [
    "ELD_DISCLAIMER",
    "honest_limits",
    "DispatchLedger",
    "Driver",
    "Load",
    "Truck",
    "default_db_path",
    "new_id",
    "LoadStatus",
    "OfferState",
    "Readiness",
    "ScheduleFit",
    "allowed_next",
    "compute_readiness",
    "is_terminal",
    "Receipt",
    "verify_chain",
    "GENESIS_HASH",
    "DispatcherTwin",
    "DispatchRefusal",
    "VerifierTwin",
    "TIGHT_BUFFER_DAYS",
    "week_board",
    "week_dates",
    "board_conflicts",
    "render_board_text",
    # Truck-dispatch MVP: route ranking, check calls / POD, encrypted ops.
    "routes",
    "checkcalls",
    "ops_server",
    "RoadNetwork",
    "SyntheticRoadNetwork",
    "RouteError",
    "FuelParams",
    "RankedRoute",
    "rank_routes",
    "Channel",
    "SimulatedChannel",
    "ChannelReceipt",
    "CheckCallRefusal",
    "CheckCallEngine",
    "DetentionPolicy",
    "OpsServer",
    "OpsAuth",
    "OpsError",
    "OpsAuthError",
]

#: The legal line, in one place. No UI copy, marketing, or response may
#: imply FMCSA/DOT compliance; the edition is awareness tooling only.
ELD_DISCLAIMER = (
    "LEVI Dispatch is not an ELD and does not connect to a vehicle's engine. "
    "It makes no claim of FMCSA/DOT compliance. Hours-of-service features "
    "(later phase) are awareness reminders only, never certified compliance."
)


def honest_limits() -> list[str]:
    """What the board does and does not do — the honest-limits sheet in code."""
    return [
        "Local-only: the ledger lives on the dispatcher's machine; no data leaves it.",
        "No metering: no seat-, vehicle-, or insight-based counters exist.",
        "Not an ELD: " + ELD_DISCLAIMER,
        "Advisory only: LEVI proposes, the dispatcher decides; no autonomous dispatch.",
        "Receipts are local tamper-evidence, not legal proof of anything.",
        "Scheduling conflicts are date-range checks on the dispatcher's own book, "
        "not live GPS or traffic awareness.",
    ]
