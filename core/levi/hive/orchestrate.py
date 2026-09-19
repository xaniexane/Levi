"""Hive orchestration — the legion coordinated as one mind.

Mechanical and honest: rule-based fan-out over the roster, no
sentience claims, mode always reported.

  * ``seats_for(wave=..., category=..., keys=...)`` — resolve a
    seat list from the roster (deny-open on bad input).
  * ``broadcast(seats, task, handler)`` — fan a task/query across
    seats and gather results with receipts: per-seat attribution,
    failures reported per seat, never swallowed.
  * ``pulse(seats)`` — the default per-seat handler: each seat's
    observable raising state (stage, learnings, seasoned). The head
    polling every head.

The ``handler`` is caller-supplied: ``handler(seat_key, task) ->
result``. The hive does not pretend seats "think" on command — it
runs the caller's function per seat and keeps honest books. One
seat's exception becomes that seat's receipt with ok=False; the
broadcast continues.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from levi.founders import roster
from levi.growth import journal as _journal


def seats_for(
    *,
    wave: Optional[str] = None,
    category: Optional[str] = None,
    keys: Optional[List[str]] = None,
) -> List[str]:
    """Resolve a seat list from the roster.

    Exactly one selector. ``wave`` in founders|A|B|C|D; ``category``
    is an automation catalog category; ``keys`` is an explicit list
    (deny-open: every key must be a real seat).
    """
    given = [s is not None for s in (wave, category, keys)]
    if sum(given) != 1:
        raise ValueError("seats_for: exactly one of wave|category|keys is required")
    if keys is not None:
        if not isinstance(keys, list) or not keys:
            raise ValueError("seats_for: keys must be a non-empty list")
        for k in keys:
            roster.get_seat(k)  # deny-open
        return list(keys)
    if wave is not None:
        if wave not in ("founders", "A", "B", "C", "D"):
            raise ValueError("seats_for: bad wave %r" % wave)
        return [s.key for s in roster.SEATS.values() if s.wave == wave]
    cats = {s.category for s in roster.SEATS.values() if s.kind == "agent"}
    if category not in cats:
        raise ValueError("seats_for: unknown category %r" % category)
    return [s.key for s in roster.SEATS.values() if s.category == category]


def pulse_handler(seat_key: str, task: Any = None) -> Dict[str, Any]:
    """Default per-seat handler: the seat's observable raising state."""
    from levi.growth.tracks import seat_stage, seat_stats, track_for

    track = track_for(seat_key)
    stats = seat_stats(seat_key)
    stage = seat_stage(seat_key)
    return {
        "seat": seat_key,
        "track": track.track_id,
        "stage": stage["name"],
        "learnings": int(stats["learnings"]),
        "seasoned": roster.is_seasoned(seat_key),
        "nature": roster.current_nature(seat_key),
        "mentee_count": len(roster.get_seat(seat_key).mentees),
    }


def broadcast(
    seats: List[str],
    task: Any,
    handler: Callable[[str, Any], Any],
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Fan ``task`` across ``seats`` via ``handler``; gather receipts.

    Returns {"task_id", "task", "mode": "rules:fan-out", "seats",
    "ok", "failed", "receipts": [...]}. Receipts are per-seat:
    {"seat", "ok", "result"|"error", "ts"}. A seat's exception is
    captured as its receipt — reported, never swallowed.
    """
    if not isinstance(seats, list) or not seats:
        raise ValueError("broadcast: seats must be a non-empty list")
    for k in seats:
        roster.get_seat(k)  # deny-open
    if not callable(handler):
        raise ValueError("broadcast: handler must be callable")
    task_id = task_id or _journal.new_cycle_id()
    receipts: List[Dict[str, Any]] = []
    for key in seats:
        try:
            result = handler(key, task)
            receipts.append(
                {"seat": key, "ok": True, "result": result, "ts": _journal.now_iso()}
            )
        except Exception as exc:
            receipts.append(
                {
                    "seat": key,
                    "ok": False,
                    "error": "%s: %s" % (type(exc).__name__, exc),
                    "ts": _journal.now_iso(),
                }
            )
    return {
        "task_id": task_id,
        "task": task,
        "mode": "rules:fan-out",
        "seats": len(seats),
        "ok": sum(1 for r in receipts if r["ok"]),
        "failed": sum(1 for r in receipts if not r["ok"]),
        "receipts": receipts,
    }


def pulse(
    *,
    wave: Optional[str] = None,
    category: Optional[str] = None,
    keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Poll a cohort's raising state: broadcast the pulse handler."""
    seats = seats_for(wave=wave, category=category, keys=keys)
    return broadcast(seats, {"kind": "pulse"}, pulse_handler, task_id="pulse")
