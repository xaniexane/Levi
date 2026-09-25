"""Twin daemons — the always-on daemon runs as an FG/BG pair.

Two daemons (e.g. one on the phone, one in the sandbox) mirror each other
through their twins: heartbeats plus state digests. If the FG daemon goes
silent past the threshold and the BG is fresh, the BG promotes. Promotion
is always explicit and recorded — a daemon never promotes itself silently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin

#: Seconds without a heartbeat before a daemon twin counts as silent.
DEFAULT_SILENCE_S = 300.0


def ensure_daemon_twins(
    lattice: TwinLattice,
    daemon_id: str = "levi-daemon",
) -> List[Twin]:
    """Create the FG/BG daemon pair. Idempotent."""
    return lattice.ensure_pair(
        "daemon", daemon_id, state={"mode": "unknown", "services_up": 0}
    )


def daemon_pulse(
    lattice: TwinLattice,
    daemon_id: str = "levi-daemon",
    side: str = "fg",
    state_update: Optional[Dict[str, Any]] = None,
) -> Twin:
    """Record a heartbeat from one side of the daemon pair."""
    return lattice.heartbeat(f"daemon:{daemon_id}:{side}", state_update)


def check_daemon_failover(
    lattice: TwinLattice,
    daemon_id: str = "levi-daemon",
    silence_s: float = DEFAULT_SILENCE_S,
) -> Optional[Dict[str, Any]]:
    """Promote the BG daemon if FG is silent and BG is alive."""
    return lattice.check_failover("daemon", daemon_id, silence_s)
