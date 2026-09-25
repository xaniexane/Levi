"""The weekly dispatch board (KFX2 workstream DISPATCH).

Reads the local ledger and renders one week of the operation: which
driver carries which load on which day, plus the conflicts the verifier
twin would refuse. Pure read-only views — the board never mutates the
ledger; mutations belong to the twin pair.

Stdlib only. Offline. The board is a local picture of a local book.
"""

from __future__ import annotations

from datetime import date, timedelta

from .ledger import DispatchLedger
from .lifecycle import LoadStatus, ScheduleFit
from .twins import VerifierTwin


def week_dates(week_start: str) -> list[date]:
    """Seven dates starting Monday ``week_start`` (ISO YYYY-MM-DD)."""
    start = date.fromisoformat(week_start)
    return [start + timedelta(days=i) for i in range(7)]


def week_board(
    ledger: DispatchLedger, week_start: str
) -> dict[str, dict[str, list[str]]]:
    """Map driver_id -> {iso_date: [load references on that day]}.

    A load occupies every day from its pickup_date through its
    delivery_date, clipped to the week. Terminal loads (invoiced,
    cancelled) are excluded — the board shows live work.
    """
    days = week_dates(week_start)
    day_set = {d.isoformat() for d in days}
    board: dict[str, dict[str, list[str]]] = {}
    for driver in ledger.list_drivers():
        board[driver.id] = {d.isoformat(): [] for d in days}
    for load in ledger.list_loads():
        if load.status in (LoadStatus.INVOICED, LoadStatus.CANCELLED):
            continue
        if not load.driver_id or load.driver_id not in board:
            continue
        if not load.pickup_date or not load.delivery_date:
            continue
        start = date.fromisoformat(load.pickup_date)
        end = date.fromisoformat(load.delivery_date)
        cursor = start
        while cursor <= end:
            iso = cursor.isoformat()
            if iso in day_set:
                board[load.driver_id][iso].append(
                    f"{load.reference} ({load.status.value})"
                )
            cursor += timedelta(days=1)
    return board


def board_conflicts(ledger: DispatchLedger) -> list[dict]:
    """Find active-load overlaps the verifier would refuse, across drivers.

    Returns one dict per clash: driver, the two load references, and the
    ternary fit. Empty list means the board is clean.
    """
    verifier = VerifierTwin(ledger)
    clashes: list[dict] = []
    for driver in ledger.list_drivers():
        active = ledger.active_loads_for_driver(driver.id)
        seen: set[str] = set()
        for load in active:
            if not load.pickup_date or not load.delivery_date:
                continue
            fit = verifier.check_schedule_fit(driver.id, load)
            if fit == ScheduleFit.CONFLICT and load.id not in seen:
                # name the actual overlapping partner for an honest report
                for other in active:
                    if other.id == load.id or other.id in seen:
                        continue
                    if not other.pickup_date or not other.delivery_date:
                        continue
                    from .twins import ranges_overlap

                    if ranges_overlap(
                        load.pickup_date,
                        load.delivery_date,
                        other.pickup_date,
                        other.delivery_date,
                    ):
                        clashes.append(
                            {
                                "driver": driver.name,
                                "load_a": load.reference,
                                "load_b": other.reference,
                                "fit": fit.value,
                            }
                        )
                        seen.add(load.id)
                        seen.add(other.id)
                        break
    return clashes


def render_board_text(ledger: DispatchLedger, week_start: str) -> str:
    """Plain-text weekly board for the dispatcher's terminal."""
    board = week_board(ledger, week_start)
    drivers = {d.id: d for d in ledger.list_drivers()}
    days = week_dates(week_start)
    lines = [f"DISPATCH BOARD — week of {week_start}", ""]
    header = "driver".ljust(14) + "".join(
        d.strftime("%a %m/%d").ljust(22) for d in days
    )
    lines.append(header)
    lines.append("-" * len(header))
    for driver_id, daymap in board.items():
        name = drivers.get(driver_id).name if driver_id in drivers else driver_id
        row = name[:13].ljust(14)
        for d in days:
            cell = ", ".join(daymap[d.isoformat()]) or "·"
            row += cell[:21].ljust(22)
        lines.append(row)
    clashes = board_conflicts(ledger)
    lines.append("")
    if clashes:
        lines.append("CONFLICTS (verifier would refuse these):")
        for c in clashes:
            lines.append(f"  {c['driver']}: {c['load_a']} overlaps {c['load_b']}")
    else:
        lines.append("no schedule conflicts.")
    return "\n".join(lines)
