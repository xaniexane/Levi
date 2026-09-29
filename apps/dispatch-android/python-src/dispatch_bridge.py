"""Dispatch Android bridge.

JSON in/out wrappers over the on-device dispatch engine:
  - board      : week board, conflicts, text render
  - loads      : book, list, advance through the twin-pair lifecycle
  - drivers    : register, list
  - trucks     : register, list
  - checkcalls : hands-off check-call processor (simulated channel only)
  - limits     : the engine's honest-limits sheet + ELD disclaimer

Every function returns a JSON string. The Java side never touches
Python objects directly. Every load mutation goes through
DispatcherTwin so the verifier twin countersigns and a receipt lands.

Hard boundaries (from the engine, restated at the surface):
  - This app is NOT an ELD and makes NO FMCSA/DOT compliance claim.
  - LEVI advises; the dispatcher decides. Nothing dispatches a load
    on its own — every transition is an explicit twin-pair call.
"""

from __future__ import annotations

import json
import traceback
from datetime import date
from pathlib import Path

_WORKSPACE: Path | None = None
_LEDGER = None
_TWINS = None
_CHECKCALLS = None


def _ws() -> Path:
    if _WORKSPACE is None:
        raise RuntimeError("workspace not set")
    return _WORKSPACE


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _lazy():
    global _LEDGER, _TWINS, _CHECKCALLS
    if _LEDGER is None:
        from levi.dispatch.ledger import DispatchLedger
        from levi.dispatch.twins import DispatcherTwin
        from levi.dispatch.checkcalls import CheckCallEngine, SimulatedChannel

        _LEDGER = DispatchLedger(_ws() / "dispatch.db")
        _TWINS = DispatcherTwin(_LEDGER)
        _CHECKCALLS = CheckCallEngine(_LEDGER, SimulatedChannel())
    return _LEDGER, _TWINS, _CHECKCALLS


def set_workspace(path: str) -> str:
    global _WORKSPACE, _LEDGER, _TWINS, _CHECKCALLS
    _WORKSPACE = Path(path)
    _WORKSPACE.mkdir(parents=True, exist_ok=True)
    _LEDGER = _TWINS = _CHECKCALLS = None
    return json.dumps({"ok": True})


def seed_demo() -> str:
    """Seed one driver, one truck, one load on first launch."""
    try:
        ledger, twins, _ = _lazy()
        if ledger.list_drivers():
            return json.dumps({"ok": True, "seeded": False})
        drv, _ = twins.register_driver("Demo Driver", phone="", home_base="Springfield IL")
        trk, _ = twins.register_truck("UNIT-01", equipment="dry_van")
        today = date.today().isoformat()
        lod, _ = twins.book_load(
            "DEMO-001", origin="Springfield, IL", destination="Chicago, IL",
            pickup_date=today, delivery_date=today,
            rate_cents=85000, notes="seeded demo load",
        )
        return json.dumps({"ok": True, "seeded": True,
                           "driver": drv.id, "truck": trk.id, "load": lod.id})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def _load_json(load) -> dict:
    return {
        "id": load.id,
        "reference": load.reference,
        "origin": load.origin,
        "destination": load.destination,
        "pickup_date": load.pickup_date,
        "delivery_date": load.delivery_date,
        "status": load.status.value,
        "offer_state": load.offer_state.value,
        "readiness": load.readiness.value,
        "driver_id": load.driver_id,
        "truck_id": load.truck_id,
        "rate_cents": load.rate_cents,
        "notes": load.notes,
    }


def list_loads() -> str:
    try:
        ledger, _, _ = _lazy()
        return json.dumps({"ok": True, "loads": [_load_json(l) for l in ledger.list_loads()]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_drivers() -> str:
    try:
        ledger, _, _ = _lazy()
        return json.dumps({"ok": True, "drivers": [
            {"id": d.id, "name": d.name, "phone": d.phone, "home_base": d.home_base}
            for d in ledger.list_drivers()]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def list_trucks() -> str:
    try:
        ledger, _, _ = _lazy()
        return json.dumps({"ok": True, "trucks": [
            {"id": t.id, "unit_number": t.unit_number, "equipment": t.equipment}
            for t in ledger.list_trucks()]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def board_text(week_start: str) -> str:
    try:
        from levi.dispatch.board import render_board_text
        ledger, _, _ = _lazy()
        return json.dumps({"ok": True, "text": render_board_text(ledger, week_start)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def conflicts() -> str:
    try:
        from levi.dispatch.board import board_conflicts
        ledger, _, _ = _lazy()
        return json.dumps({"ok": True, "conflicts": board_conflicts(ledger)})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def book_load(reference: str, origin: str, destination: str,
              pickup_date: str, delivery_date: str,
              rate_dollars: str, notes: str) -> str:
    try:
        _, twins, _ = _lazy()
        cents = int(float(rate_dollars or "0") * 100)
        load, receipt = twins.book_load(
            reference, origin=origin, destination=destination,
            pickup_date=pickup_date, delivery_date=delivery_date,
            rate_cents=cents, notes=notes)
        return json.dumps({"ok": True, "load": _load_json(load),
                           "receipt_seq": receipt.seq})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def allowed_moves(load_id: str) -> str:
    try:
        from levi.dispatch.lifecycle import allowed_next
        ledger, _, _ = _lazy()
        load = ledger.get_load(load_id)
        if load is None:
            return json.dumps({"ok": False, "error": "unknown load"})
        return json.dumps({"ok": True, "status": load.status.value,
                           "next": sorted(s.value for s in allowed_next(load.status))})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# Map a target status to the twin-pair call that performs it.
_ADVANCE = {
    "dispatched": "dispatch_load",
    "picked_up": "record_pickup",
    "in_transit": "record_departure",
    "delivered": "record_delivery",
    "invoiced": "record_invoice",
    "cancelled": "cancel_load",
}


def accept_offer(load_id: str, rate_dollars: str) -> str:
    """Accept the load's offer (twin-pair). Required before dispatch."""
    try:
        _, twins, _ = _lazy()
        cents = int(float(rate_dollars or "0") * 100) if rate_dollars else None
        load, receipt = twins.accept_offer(load_id, cents)
        return json.dumps({"ok": True, "load": _load_json(load),
                           "receipt_seq": receipt.seq})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def advance_load(load_id: str, to_status: str) -> str:
    """Advance a load via the twin pair. Refusals come back as errors."""
    try:
        _, twins, _ = _lazy()
        meth = _ADVANCE.get(to_status)
        if meth is None:
            return json.dumps({"ok": False, "error": f"no twin move for {to_status!r}"})
        if to_status == "cancelled":
            load, receipt = getattr(twins, meth)(load_id, "cancelled from app")
        else:
            load, receipt = getattr(twins, meth)(load_id)
        return json.dumps({"ok": True, "load": _load_json(load),
                           "receipt_seq": receipt.seq})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def register_driver(name: str, phone: str, home_base: str) -> str:
    try:
        _, twins, _ = _lazy()
        drv, receipt = twins.register_driver(name, phone=phone, home_base=home_base)
        return json.dumps({"ok": True, "id": drv.id, "receipt_seq": receipt.seq})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def register_truck(unit_number: str, equipment: str) -> str:
    try:
        _, twins, _ = _lazy()
        trk, receipt = twins.register_truck(unit_number, equipment=equipment or "dry_van")
        return json.dumps({"ok": True, "id": trk.id, "receipt_seq": receipt.seq})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def assign_load(load_id: str, driver_id: str, truck_id: str) -> str:
    """Assign driver + truck to a load (twin-pair, schedule-fit checked)."""
    try:
        from levi.dispatch.lifecycle import ScheduleFit
        ledger, twins, _ = _lazy()
        load = ledger.get_load(load_id)
        if load is None:
            return json.dumps({"ok": False, "error": "unknown load"})
        fit = twins.verifier.check_assignment(load, driver_id)
        if fit is ScheduleFit.CONFLICT:
            return json.dumps({"ok": False,
                               "error": f"refused: schedule fit is {fit.value}"})
        load.driver_id = driver_id
        load.truck_id = truck_id or None
        load.refresh_readiness()
        ledger.update_load(load)
        return json.dumps({"ok": True, "load": _load_json(load),
                           "schedule_fit": fit.value})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def checkcall(load_id: str, event: str) -> str:
    """Record a check-call event (picked_up / depart_pickup). Simulated channel."""
    try:
        _, _, cc = _lazy()
        if event == "picked_up":
            receipt = cc.mark_picked_up(load_id)
        elif event == "depart_pickup":
            receipt = cc.depart(load_id, "pickup")
        else:
            return json.dumps({"ok": False, "error": f"unknown event {event!r}"})
        return json.dumps({"ok": True, "channel": receipt.channel,
                           "sent_to": receipt.recipient,
                           "message": receipt.message})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def honest_limits() -> str:
    try:
        from levi.dispatch import honest_limits as _hl, ELD_DISCLAIMER
        return json.dumps({"ok": True, "limits": _hl(), "eld": ELD_DISCLAIMER})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def today_iso() -> str:
    return json.dumps({"ok": True, "today": date.today().isoformat()})
