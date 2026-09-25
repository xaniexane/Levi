"""Local SQLite ledger for dispatch operations (KFX2 workstream DISPATCH).

The single source of truth for the board: drivers, trucks, loads, and
the receipt chain. Local-first by construction — the database file lives
on the dispatcher's own machine (default ``~/.levi/dispatch/dispatch.db``,
overridable with ``LEVI_DISPATCH_DB``), nothing is sent anywhere, and
there is nothing to meter: no seat-, vehicle-, or insight-based counters
exist in this schema on purpose.

Stdlib only (sqlite3). All writes go through the twin pair in
:mod:`levi.dispatch.twins`, never by raw SQL from callers.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .lifecycle import LoadStatus, OfferState, Readiness, compute_readiness
from .receipts import GENESIS_HASH, Receipt

SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    home_base TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS trucks (
    id TEXT PRIMARY KEY,
    unit_number TEXT NOT NULL,
    equipment TEXT NOT NULL DEFAULT 'dry_van',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS loads (
    id TEXT PRIMARY KEY,
    reference TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT '',
    destination TEXT NOT NULL DEFAULT '',
    pickup_date TEXT NOT NULL DEFAULT '',
    delivery_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'booked',
    offer_state TEXT NOT NULL DEFAULT 'negotiating',
    readiness TEXT NOT NULL DEFAULT 'blocked',
    driver_id TEXT,
    truck_id TEXT,
    rate_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS receipts (
    seq INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    twin_a TEXT NOT NULL,
    twin_b TEXT NOT NULL,
    load_id TEXT NOT NULL,
    action TEXT NOT NULL,
    from_state TEXT NOT NULL DEFAULT '',
    to_state TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    override = os.environ.get("LEVI_DISPATCH_DB")
    if override:
        return Path(override)
    return Path.home() / ".levi" / "dispatch" / "dispatch.db"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class Driver:
    id: str
    name: str
    phone: str = ""
    home_base: str = ""
    active: bool = True


@dataclass
class Truck:
    id: str
    unit_number: str
    equipment: str = "dry_van"
    active: bool = True


@dataclass
class Load:
    id: str
    reference: str
    origin: str = ""
    destination: str = ""
    pickup_date: str = ""
    delivery_date: str = ""
    status: LoadStatus = LoadStatus.BOOKED
    offer_state: OfferState = OfferState.NEGOTIATING
    readiness: Readiness = Readiness.BLOCKED
    driver_id: str | None = None
    truck_id: str | None = None
    rate_cents: int = 0
    notes: str = ""

    def refresh_readiness(self) -> None:
        self.readiness = compute_readiness(
            origin=self.origin or None,
            destination=self.destination or None,
            pickup_date=self.pickup_date or None,
            delivery_date=self.delivery_date or None,
            driver_id=self.driver_id,
            truck_id=self.truck_id,
        )


class DispatchLedger:
    """The dispatcher's local book. One file, zero network."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    # -- low-level helpers -------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- drivers / trucks ---------------------------------------------------
    def add_driver(self, driver: Driver) -> Driver:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO drivers (id, name, phone, home_base, active)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    driver.id,
                    driver.name,
                    driver.phone,
                    driver.home_base,
                    int(driver.active),
                ),
            )
        return driver

    def add_truck(self, truck: Truck) -> Truck:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO trucks (id, unit_number, equipment, active)"
                " VALUES (?, ?, ?, ?)",
                (truck.id, truck.unit_number, truck.equipment, int(truck.active)),
            )
        return truck

    def get_driver(self, driver_id: str) -> Driver | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM drivers WHERE id = ?", (driver_id,)
            ).fetchone()
        if row is None:
            return None
        return Driver(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            home_base=row["home_base"],
            active=bool(row["active"]),
        )

    def get_truck(self, truck_id: str) -> Truck | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trucks WHERE id = ?", (truck_id,)
            ).fetchone()
        if row is None:
            return None
        return Truck(
            id=row["id"],
            unit_number=row["unit_number"],
            equipment=row["equipment"],
            active=bool(row["active"]),
        )

    def list_drivers(self, active_only: bool = True) -> list[Driver]:
        q = (
            "SELECT * FROM drivers"
            + (" WHERE active = 1" if active_only else "")
            + " ORDER BY name"
        )
        with self._connect() as conn:
            rows = conn.execute(q).fetchall()
        return [
            Driver(
                id=r["id"],
                name=r["name"],
                phone=r["phone"],
                home_base=r["home_base"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    def list_trucks(self, active_only: bool = True) -> list[Truck]:
        q = (
            "SELECT * FROM trucks"
            + (" WHERE active = 1" if active_only else "")
            + " ORDER BY unit_number"
        )
        with self._connect() as conn:
            rows = conn.execute(q).fetchall()
        return [
            Truck(
                id=r["id"],
                unit_number=r["unit_number"],
                equipment=r["equipment"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    # -- loads ---------------------------------------------------------------
    def add_load(self, load: Load) -> Load:
        load.refresh_readiness()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO loads (id, reference, origin, destination, pickup_date,"
                " delivery_date, status, offer_state, readiness, driver_id, truck_id,"
                " rate_cents, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    load.id,
                    load.reference,
                    load.origin,
                    load.destination,
                    load.pickup_date,
                    load.delivery_date,
                    load.status.value,
                    load.offer_state.value,
                    load.readiness.value,
                    load.driver_id,
                    load.truck_id,
                    load.rate_cents,
                    load.notes,
                ),
            )
        return load

    def update_load(self, load: Load) -> Load:
        load.refresh_readiness()
        with self._connect() as conn:
            conn.execute(
                "UPDATE loads SET reference=?, origin=?, destination=?, pickup_date=?,"
                " delivery_date=?, status=?, offer_state=?, readiness=?, driver_id=?,"
                " truck_id=?, rate_cents=?, notes=? WHERE id=?",
                (
                    load.reference,
                    load.origin,
                    load.destination,
                    load.pickup_date,
                    load.delivery_date,
                    load.status.value,
                    load.offer_state.value,
                    load.readiness.value,
                    load.driver_id,
                    load.truck_id,
                    load.rate_cents,
                    load.notes,
                    load.id,
                ),
            )
        return load

    def get_load(self, load_id: str) -> Load | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM loads WHERE id = ?", (load_id,)
            ).fetchone()
        return _row_to_load(row) if row else None

    def list_loads(
        self,
        *,
        status: LoadStatus | None = None,
        driver_id: str | None = None,
    ) -> list[Load]:
        q = "SELECT * FROM loads"
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if driver_id is not None:
            clauses.append("driver_id = ?")
            params.append(driver_id)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY pickup_date, reference"
        with self._connect() as conn:
            rows = conn.execute(q, params).fetchall()
        return [_row_to_load(r) for r in rows]

    def active_loads_for_driver(self, driver_id: str) -> list[Load]:
        """Non-terminal loads assigned to a driver (the scheduling set)."""
        terminal = [s.value for s in (LoadStatus.INVOICED, LoadStatus.CANCELLED)]
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM loads WHERE driver_id = ? AND status NOT IN (?, ?)"
                " ORDER BY pickup_date",
                (driver_id, *terminal),
            ).fetchall()
        return [_row_to_load(r) for r in rows]

    # -- receipts --------------------------------------------------------------
    def record_receipt(self, receipt: Receipt) -> Receipt:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO receipts (seq, ts, twin_a, twin_b, load_id, action,"
                " from_state, to_state, details_json, prev_hash, hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.seq,
                    receipt.ts,
                    receipt.twin_a,
                    receipt.twin_b,
                    receipt.load_id,
                    receipt.action,
                    receipt.from_state,
                    receipt.to_state,
                    json.dumps(receipt.details, sort_keys=True),
                    receipt.prev_hash,
                    receipt.hash,
                ),
            )
        return receipt

    def last_receipt_hash(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT hash FROM receipts ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return row["hash"] if row else GENESIS_HASH

    def next_receipt_seq(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS m FROM receipts"
            ).fetchone()
        return int(row["m"]) + 1

    def receipt_chain(self, load_id: str | None = None) -> list[Receipt]:
        q = "SELECT * FROM receipts"
        params: list[Any] = []
        if load_id is not None:
            q += " WHERE load_id = ?"
            params.append(load_id)
        q += " ORDER BY seq"
        with self._connect() as conn:
            rows = conn.execute(q, params).fetchall()
        out: list[Receipt] = []
        for r in rows:
            out.append(
                Receipt(
                    seq=r["seq"],
                    ts=r["ts"],
                    twin_a=r["twin_a"],
                    twin_b=r["twin_b"],
                    load_id=r["load_id"],
                    action=r["action"],
                    from_state=r["from_state"],
                    to_state=r["to_state"],
                    details=json.loads(r["details_json"] or "{}"),
                    prev_hash=r["prev_hash"],
                    hash=r["hash"],
                )
            )
        return out


def _row_to_load(row: sqlite3.Row) -> Load:
    return Load(
        id=row["id"],
        reference=row["reference"],
        origin=row["origin"],
        destination=row["destination"],
        pickup_date=row["pickup_date"],
        delivery_date=row["delivery_date"],
        status=LoadStatus(row["status"]),
        offer_state=OfferState(row["offer_state"]),
        readiness=Readiness(row["readiness"]),
        driver_id=row["driver_id"],
        truck_id=row["truck_id"],
        rate_cents=row["rate_cents"],
        notes=row["notes"],
    )
