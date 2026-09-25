#!/usr/bin/env python3
"""Fleet node runner — join this machine to the LEVI mesh as a worker.

Worker-only: offers spare compute and runs registered task functions
for farmers. (Farm XOR work: a node that both farms and works shares
one inbox between the farmer loop and the worker thread, so it can
steal its own messages — documented prototype limit.)

Usage:
    python run_node.py --config node_config.json

The runner never touches anything outside its own folder and the
data_dir named in the config: no install, no admin rights, nothing
that can disturb software already on the machine.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mesh.node import MeshNode  # noqa: E402
from mesh.resources import ResourceOffer  # noqa: E402
from mesh.tasks import Worker  # noqa: E402
from mesh.transport import LanTransport, LocalTransport, TransportUnavailable  # noqa: E402

DEFAULT_PORT = 47911


def load_config(path: Path) -> dict:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(
            f"[node] config not found: {path}\n"
            "       copy node_config.example.json to node_config.json and edit it."
        )
    except ValueError as exc:
        sys.exit(f"[node] config is not valid JSON: {exc}")
    if not isinstance(cfg, dict):
        sys.exit("[node] config must be a JSON object.")
    return cfg


def build_transport(cfg: dict):
    kind = str(cfg.get("transport", "lan")).lower()
    if kind == "lan":
        peers = []
        for p in cfg.get("known_peers", []):
            try:
                host, port = p[0], int(p[1])
            except (TypeError, IndexError, ValueError):
                sys.exit(f"[node] bad known_peers entry (want [host, port]): {p!r}")
            peers.append((host, port))
        return LanTransport(
            bind_host=str(cfg.get("bind_host", "0.0.0.0")),
            bind_port=int(cfg.get("bind_port", DEFAULT_PORT)),
            known_peers=peers,
        )
    if kind == "local":
        return LocalTransport()
    sys.exit(f"[node] unknown transport {kind!r} (want 'lan' or 'local').")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Join this machine to the LEVI fleet mesh."
    )
    ap.add_argument(
        "--config", default="node_config.json", help="path to node_config.json"
    )
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    device_id = str(cfg.get("device_id", "")).strip()
    device_name = str(cfg.get("device_name", device_id)).strip()
    if not device_id:
        sys.exit("[node] config needs a non-empty device_id.")

    data_dir = Path(str(cfg.get("data_dir", "mesh_data"))).resolve()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.exit(f"[node] cannot create data_dir {data_dir}: {exc}")

    transport = build_transport(cfg)
    node = MeshNode(
        device_id=device_id,
        device_name=device_name,
        transport=transport,
        heartbeat_interval=float(cfg.get("heartbeat_interval", 5.0)),
    )

    offer_cfg = cfg.get("offer", {})
    offer = ResourceOffer(
        node_id=node.node_id,
        cpu_units=float(offer_cfg.get("cpu_units", 1.0)),
        memory_mb=float(offer_cfg.get("memory_mb", 512.0)),
        storage_mb=float(offer_cfg.get("storage_mb", 10240.0)),
        bandwidth_kbps=float(offer_cfg.get("bandwidth_kbps", 0.0)),
        tags=tuple(offer_cfg.get("tags", ("worker",))),
    ).to_dict()

    try:
        node.join(offer=offer)
    except (TransportUnavailable, OSError) as exc:
        sys.exit(
            f"[node] could not bind/listen: {exc}\n"
            "       is the port already in use? check bind_port in the config."
        )

    worker = Worker(node).start()
    listen_port = getattr(transport, "_tcp_port", "?")
    free_mb = shutil.disk_usage(data_dir).free // (1024 * 1024)

    print(f"[node] {device_name} joined the fleet as {node.node_id[:12]}…")
    print(
        f"[node] listening on port {listen_port}; data dir {data_dir} ({free_mb} MB free)"
    )
    print(
        f"[node] offering {offer['cpu_units']} cpu / {offer['memory_mb']} MB ram / "
        f"{offer['storage_mb']} MB storage; tags={list(offer['tags'])}"
    )
    print("[node] working tasks for the fleet — Ctrl+C to leave cleanly.")

    try:
        last = 0.0
        while True:
            time.sleep(1.0)
            now = time.time()
            if now - last >= 30.0:
                last = now
                try:
                    peers = node.discover(timeout=1.0)
                except Exception:
                    peers = []
                print(f"[node] heartbeat ok — {len(peers)} peer(s) visible")
    except KeyboardInterrupt:
        print("\n[node] leaving the fleet…")
    finally:
        worker.stop()
        node.leave()
        print("[node] left cleanly.")


if __name__ == "__main__":
    main()
