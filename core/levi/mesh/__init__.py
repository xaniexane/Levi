"""Fleet mesh — the golden brick road (Chauncey, 2026-09-18).

THE FLEET IS THE CLOUD: a cooperative mesh where every user's device
contributes idle compute/storage/bandwidth. There is no datacenter to
pay for because there is no datacenter — the cloud is produced purely
from the fleet's spare capacity, out of thin air.

Doctrine:
* Gateway Law — the mesh is fleet-internal only. It never touches
  outside systems directly; external access stays behind the Cybrus
  gateway. A test asserts this package imports no network clients.
* Founder-gating — mesh internals (ledger truth, trust flags) are
  founder-visible; the public surface is minimal.
* Contribute-to-earn — contributed work earns free credits, settled
  into the catalogue credit wallet (same doctrine, same caps).

Honest limits (prototype scope): localhost/LAN transport only.
NAT traversal, mobile radio/battery constraints, Sybil resistance,
and the real onion transport are out of scope — documented where
they bite. The transport abstraction accepts a real deep-web lane
later without changing anything above it.
"""

from __future__ import annotations

from .ledger import ContributionLedger
from .node import MeshNode
from .resources import ResourceOffer, ResourcePool
from .tasks import TaskFarmer, TaskSpec, chunk_bytes
from .transport import DeepWebTransport, LanTransport, LocalTransport, Transport
from .trust import TrustMonitor

__all__ = [
    "MeshNode",
    "Transport",
    "LocalTransport",
    "LanTransport",
    "DeepWebTransport",
    "ResourceOffer",
    "ResourcePool",
    "TaskSpec",
    "TaskFarmer",
    "chunk_bytes",
    "ContributionLedger",
    "TrustMonitor",
]
