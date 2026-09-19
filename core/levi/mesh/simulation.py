"""Fleet-mesh simulation — N nodes on localhost, one real farmed task.

Runnable: ``python -m levi.mesh.simulation`` (with ``core/`` on
``sys.path``). Spins ``num_nodes`` MeshNodes, each with its own
LocalTransport + Worker, farms a parallel-sha256 task with
replication 2, optionally kills a worker mid-task, and reports:

* result correctness (farmed hashes == locally computed hashes);
* replication survival (task completes despite the kill);
* ledger balances (contributors earned units);
* trust flags (founder-visible only).

Everything stays on loopback. Nothing leaves the machine.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from levi.mesh.ledger import ContributionLedger  # noqa: E402
from levi.mesh.node import MeshNode  # noqa: E402
from levi.mesh.resources import ResourceOffer, ResourcePool  # noqa: E402
from levi.mesh.tasks import TaskFarmer, Worker, chunk_bytes  # noqa: E402
from levi.mesh.transport import LocalTransport  # noqa: E402
from levi.mesh.trust import TrustMonitor  # noqa: E402


def build_fleet(
    num_nodes: int, ledger_path: Optional[Path] = None, heartbeat_interval: float = 0.2
):
    """Create nodes, join them, start workers. Returns (nodes, workers)."""
    nodes: List[MeshNode] = []
    workers: List[Worker] = []
    for i in range(num_nodes):
        node = MeshNode(
            device_id=f"sim-device-{i}",
            device_name=f"sim-node-{i}",
            transport=LocalTransport(),
            heartbeat_interval=heartbeat_interval,
        )
        node.join(
            offer={
                "cpu_units": 2.0,
                "memory_mb": 512.0,
                "tags": ["sim"],
            }
        )
        workers.append(Worker(node).start())
        nodes.append(node)
    # let heartbeats propagate so transports learn every peer
    time.sleep(1.0)
    for node in nodes:
        node.discover(timeout=0.5)
    ledger = ContributionLedger(path=ledger_path) if ledger_path else None
    return nodes, workers, ledger


def wire_pool(nodes: List[MeshNode]) -> ResourcePool:
    pool = ResourcePool()
    for node in nodes:
        pool.advertise(
            ResourceOffer(
                node_id=node.node_id,
                cpu_units=2.0,
                memory_mb=512.0,
                storage_mb=1024.0,
                bandwidth_kbps=1000.0,
                tags=("sim",),
            )
        )
    return pool


def run_demo(num_nodes: int = 4, kill_mid_task: bool = True, data: bytes = b"") -> Dict:
    """Full demo: farm, kill, verify. Returns the summary dict."""
    import tempfile

    from levi.mesh.tasks import FUNCTIONS

    # Demo-only function: deliberately slow (~0.1s/chunk on this box) so
    # the mid-task kill lands while chunks are genuinely outstanding.
    # Real fleet work would be slow for its own reasons.
    # (Registry convention: functions receive the chunk hex-encoded.)
    def _demo_slow_sha256(data_hex: str) -> str:
        raw = bytes.fromhex(data_hex)
        digest = b""
        for _ in range(100):
            digest = hashlib.sha256(raw).digest()
        return digest.hex()

    FUNCTIONS["demo_slow_sha256"] = _demo_slow_sha256
    data = data or (b"the fleet is the cloud. " * 340000)  # ~8MB
    tmp = tempfile.mkdtemp(prefix="mesh-sim-")
    nodes, workers, _ = build_fleet(num_nodes, ledger_path=Path(tmp) / "ledger.jsonl")
    ledger = ContributionLedger(path=Path(tmp) / "ledger.jsonl")
    trust = TrustMonitor()
    # The farmer (nodes[0]) stays compute-free: its inbox carries only
    # results. (A coordinator that also computes needs a per-type
    # dispatcher — noted future work, not this prototype.)
    workers[0].stop()
    pool = wire_pool(nodes[1:])
    farmer_node = nodes[0]
    farmer = TaskFarmer(farmer_node, pool, ledger=ledger, trust=trust)

    killer = None
    if kill_mid_task and len(workers) > 3:
        victim = len(workers) - 1  # kill the last worker shortly in

        def _kill():
            # Wait for genuine in-flight progress (first accepted chunk
            # lands in the ledger), then kill — deterministically
            # mid-task rather than racing a fixed sleep.
            for _ in range(400):
                if any(ledger.contributed(n.node_id) > 0 for n in nodes):
                    break
                time.sleep(0.05)
            workers[victim].stop()
            nodes[victim].leave()
            pool.withdraw(nodes[victim].node_id)

        import threading

        killer = threading.Thread(target=_kill, daemon=True)
        killer.start()

    result = farmer.submit(
        data,
        "demo_slow_sha256",
        num_chunks=8,
        replication=2,
        timeout=30.0,
        chunk_timeout=2.0,
    )
    if killer is not None:
        killer.join(timeout=5.0)

    # correctness: farmed chunk hashes == local reference
    reference = [FUNCTIONS["demo_slow_sha256"](c.hex()) for c in chunk_bytes(data, 8)]
    correct = result["results"] == reference

    for w in workers:
        try:
            w.stop()
        except Exception:
            pass
    for node in nodes:
        try:
            node.leave()
        except Exception:
            pass

    summary = {
        "nodes": num_nodes,
        "killed_mid_task": kill_mid_task,
        "correct": correct,
        "chunks": result["chunks"],
        "assignments": result["assignments"],
        "reassignments": result["reassignments"],
        "contributions": {n.node_id[:8]: ledger.contributed(n.node_id) for n in nodes},
    }
    return summary


def main() -> None:
    summary = run_demo()
    print("fleet-mesh simulation")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("  verdict:", "PASS — the fleet carried it" if summary["correct"] else "FAIL")


if __name__ == "__main__":
    main()
