"""Triads — every agent binds a twin daemon and an OS-shell twin.

Each agent of the swarm carries a triad::

    agent twin (FG/BG)  +  daemon twin (FG/BG)  +  OS-shell twin (FG/BG)

The triad is the unit of camouflage: what looks like many independent
agents, daemons, and shells is one bound triple per agent — and all
triples converge into the three Ones (see :mod:`levi.twins.convergence`).
"""

from __future__ import annotations

from typing import Dict, List

from levi.twins import agents as twin_agents
from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin


def triad_daemon_subject(agent: str) -> str:
    return f"{agent}-daemon"


def triad_shell_subject(agent: str) -> str:
    return f"os-{agent}"


def register_agent(lattice: TwinLattice, agent: str) -> Dict[str, List[Twin]]:
    """Bind one agent's triad. New agents can join the swarm at any time —
    the lattice expands outward; the Ones absorb without bound."""
    agent = agent.strip().lower().replace(" ", "-")
    if not agent:
        raise ValueError("agent name must not be empty")
    lattice.ensure_pair(
        "agent",
        agent,
        state={"status": "unknown", "load": 0.0, "capabilities": []},
    )
    daemon_pair = lattice.ensure_pair(
        "daemon",
        triad_daemon_subject(agent),
        state={"mode": "unknown", "bound_agent": agent},
    )
    shell_pair = lattice.ensure_pair(
        "shell",
        triad_shell_subject(agent),
        state={
            "cwd": "",
            "history": [],
            "jobs": [],
            "bound_agent": agent,
            "os": True,
        },
    )
    return {
        "agent": lattice.list(kind="agent", subject=agent),
        "daemon": daemon_pair,
        "shell": shell_pair,
    }


def ensure_triads(lattice: TwinLattice) -> Dict[str, Dict[str, List[Twin]]]:
    """Bind every swarm agent to its daemon twin and OS-shell twin.

    Idempotent. Delegates per agent to :func:`register_agent` so new
    agents join the same way the canon seven did.
    """
    twin_agents.ensure_agent_twins(lattice)
    return {agent: register_agent(lattice, agent) for agent in twin_agents.SWARM}


def get_triad(lattice: TwinLattice, agent: str) -> Dict[str, List[Twin]]:
    """Fetch the bound triad for one agent (empty lists if not ensured)."""
    return {
        "agent": lattice.list(kind="agent", subject=agent),
        "daemon": lattice.list(kind="daemon", subject=triad_daemon_subject(agent)),
        "shell": lattice.list(kind="shell", subject=triad_shell_subject(agent)),
    }


def triad_counts(lattice: TwinLattice) -> Dict[str, int]:
    """How many twins of each kind are bound into triads."""
    n = len(twin_agents.SWARM)
    return {"agent": 2 * n, "daemon": 2 * n, "shell": 2 * n}
