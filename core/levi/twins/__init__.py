"""The Twin Lattice — SER-21 twin architecture, LEVI-native.

Every runtime entity runs twinned: a **foreground (FG)** twin that acts and
a **background (BG)** twin that shadows, so nothing critical ever runs
single. Grounded in SER-21 (the World Model): shells are identity
containers and every shell carries the FG/BG duality.

Fleets:
    twin agents  — FG/BG pair per agent of the swarm
    twin daemons — FG/BG pair for the always-on daemon
    twin shells  — 6 shells, i.e. 3 FG/BG twin pairs

Every agent also binds a triad (see :mod:`levi.twins.triads`): its agent
twin, a twin daemon, and an OS-shell twin. All triads converge into the
three Ones (see :mod:`levi.twins.convergence`) — the All-in-One Agent,
Daemon, and OS Shell. The lattice is camouflage: many seen, three true.
Only the creator seed reproduces the arrangement.

All state is local (``~/.levi/twins/``, ``$LEVI_TWINS_HOME`` override).
Stdlib only. Twins never execute anything; they are state mirrors.
Failover is explicit: :func:`lattice.TwinLattice.promote`.
"""

from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin, twin_id_for

__all__ = ["Twin", "TwinLattice", "twin_id_for"]
