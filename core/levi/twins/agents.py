"""Twin agents — an FG/BG pair per agent of the swarm.

The FG twin is the live mirror of the agent: status, load, capabilities,
last task. The BG twin shadows it and can also run what-if simulations
without touching the live agent. Routers consult FG twins for dispatch;
BG twins are the failover.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin

#: The canonical swarm (PROJECT IDENTITY: Levi AI, 2026-07-27).
SWARM = ("echo", "alpha", "cybrus", "kai", "titan", "nexus", "aether")


def ensure_agent_twins(
    lattice: TwinLattice,
    names: Optional[List[str]] = None,
) -> Dict[str, List[Twin]]:
    """Create FG/BG pairs for every agent. Idempotent."""
    out: Dict[str, List[Twin]] = {}
    for name in names or list(SWARM):
        out[name] = lattice.ensure_pair(
            "agent",
            name,
            state={"status": "unknown", "load": 0.0, "capabilities": []},
        )
    return out


def agent_status(
    lattice: TwinLattice,
    name: str,
    status: str,
    load: float = 0.0,
    capabilities: Optional[List[str]] = None,
    task: str = "",
) -> Twin:
    """Heartbeat the FG twin of an agent with fresh state."""
    state: Dict[str, object] = {"status": status, "load": load}
    if capabilities is not None:
        state["capabilities"] = capabilities
    if task:
        state["task"] = task
    return lattice.heartbeat(f"agent:{name}:fg", state)


def dispatch_candidates(lattice: TwinLattice) -> List[Twin]:
    """FG agent twins sorted by load — who should take the next task."""
    fg = lattice.list(kind="agent", side="fg")
    return sorted(fg, key=lambda t: float(t.state.get("load", 0.0)))
