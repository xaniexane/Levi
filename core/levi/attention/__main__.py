"""CLI: ``python -m levi.attention`` — the quiet channel, demonstrated."""

from __future__ import annotations

import argparse

from levi.attention.ritual import RitualError, answer, confirm, probe
from levi.attention.signal import AttentionBus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="levi.attention", description="Addressed wake-signaling demo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="run the quiet-channel and handshake demo")
    args = ap.parse_args(argv)

    bus = AttentionBus()
    bus.subscribe(("growth", "tick"), "growth-cycle")
    bus.subscribe(("mesh", "pair"), "fleet-node")
    bus.subscribe(("news", "refresh"), "news-ingest")

    print("--- the quiet channel: only the addressed wakes ---")
    print("signal ('growth','tick') ->", bus.signal(("growth", "tick"), {"budget": 40}))
    print("signal ('news','refresh') ->", bus.signal(("news", "refresh")))
    print("signal ('nobody','home')  ->", bus.signal(("nobody", "home")))
    print("audit:", bus.audit())

    print()
    print("--- the answer-tone ritual: probe -> answer -> confirm ---")
    p = probe("node-alpha", ["store", "compute", "relay"])
    a = answer("node-beta", p, ["compute", "relay"], terms="credits-for-spare")
    try:
        s = confirm(p, a)
        print(f"session: {s.initiator} <-> {s.responder}, shared={sorted(s.shared)}, terms={s.terms!r}")
    except RitualError as e:
        print(f"aborted honestly: {e}")

    print()
    print("--- honest abort: no shared capability ---")
    p2 = probe("node-gamma", ["store"])
    a2 = answer("node-delta", p2, ["compute"])
    try:
        confirm(p2, a2)
    except RitualError as e:
        print(f"aborted honestly: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
