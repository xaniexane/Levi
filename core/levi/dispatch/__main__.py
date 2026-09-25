"""Demo CLI for the dispatch board (new file; does not touch the main CLI).

Usage:
    python -m levi.dispatch demo
        Seeds a 5-truck week of loads in a throwaway database, runs one
        load through the full lifecycle, and prints the weekly board.

    python -m levi.dispatch board <week_start> [db_path]
        Prints the weekly board for an existing ledger database.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from . import (
    DispatchLedger,
    DispatcherTwin,
    DispatchRefusal,
    honest_limits,
    render_board_text,
    verify_chain,
)


def seed_week(tmp: Path) -> DispatchLedger:
    ledger = DispatchLedger(tmp / "dispatch.db")
    twin = DispatcherTwin(ledger)

    drivers = []
    for name, base in [
        ("Maya R.", "Springfield"),
        ("Devon K.", "St. Louis"),
        ("Priya S.", "Chicago"),
        ("Tom H.", "Kansas City"),
        ("Alba M.", "Memphis"),
    ]:
        driver, _ = twin.register_driver(name, home_base=base)
        drivers.append(driver)
    trucks = []
    for unit in ["T-101", "T-102", "T-103", "T-104", "T-105"]:
        truck, _ = twin.register_truck(unit)
        trucks.append(truck)

    week = [
        ("LD-2401", "Chicago", "Dallas", "2026-09-21", "2026-09-23", 185000),
        ("LD-2402", "St. Louis", "Atlanta", "2026-09-22", "2026-09-24", 162000),
        ("LD-2403", "Kansas City", "Denver", "2026-09-23", "2026-09-25", 141000),
        ("LD-2404", "Memphis", "Houston", "2026-09-21", "2026-09-22", 98000),
        ("LD-2405", "Springfield", "Nashville", "2026-09-24", "2026-09-25", 74000),
        ("LD-2406", "Chicago", "Minneapolis", "2026-09-25", "2026-09-26", 69000),
    ]
    for i, (ref, org, dst, pu, dl, rate) in enumerate(week):
        load, _ = twin.book_load(
            ref,
            origin=org,
            destination=dst,
            pickup_date=pu,
            delivery_date=dl,
            rate_cents=rate,
        )
        load, _ = twin.offer_load(load.id, drivers[i % 5].id, trucks[i % 5].id)
        twin.accept_offer(load.id)

    # Run the first load all the way to invoiced — the milestone's proof.
    first = ledger.list_loads()[0]
    twin.dispatch_load(first.id)
    twin.record_pickup(first.id)
    twin.record_departure(first.id)
    twin.record_delivery(first.id)
    twin.record_invoice(first.id)
    return ledger


def cmd_demo() -> int:
    with tempfile.TemporaryDirectory(prefix="dispatch-demo-") as tmp:
        ledger = seed_week(Path(tmp))
        print(render_board_text(ledger, "2026-09-21"))
        print()
        ok, reason = verify_chain(ledger.receipt_chain())
        print(f"receipt chain: {'INTACT' if ok else 'BROKEN — ' + reason}")
        print(f"receipts recorded: {len(ledger.receipt_chain())}")
        print()
        print("honest limits:")
        for limit in honest_limits():
            print(f"  - {limit}")
    return 0


def cmd_board(week_start: str, db_path: str) -> int:
    ledger = DispatchLedger(Path(db_path))
    print(render_board_text(ledger, week_start))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] == "demo":
        return cmd_demo()
    if argv[0] == "board" and len(argv) >= 2:
        return cmd_board(
            argv[1], argv[2] if len(argv) > 2 else str(DispatchLedger().path)
        )
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DispatchRefusal as e:
        print(e, file=sys.stderr)
        raise SystemExit(1) from None
