"""healing_mortar — reactive-reserve self-healing record store.

Studied from: lost-crafts-20260916 — report.md [Batch 3] (Hot-Lime Mortar).

Load-bearing idea: hot-lime mortars carry *reactive reserve* — unreacted
lime that, years later, re-carbonates and heals cracks on its own.
LEVI's take: ``MortarStore`` keeps a checksum-sealed record wall plus a
reactive reserve — a shadow copy of every record as written, held back
and never touched by normal reads. A ``repair`` pass sweeps the wall,
detects cracked records (checksum mismatch, missing fields, truncated
bodies), and heals them from the reserve. Healing is honest: healed
records are marked ``healed=True`` with a repair log entry, and the
reserve is finite — every heal consumes reserve material, so a wall
that cracks faster than it is repointed eventually shows its scars.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/healing-mortar"

REQUIRED_FIELDS = ("id", "body", "created_at")


def _checksum(record: Dict) -> str:
    """Checksum over the load-bearing fields, excluding seal metadata."""
    payload = "|".join(str(record.get(k, "")) for k in REQUIRED_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class RepairEntry:
    """One healing event: what cracked, how it was healed, and when."""

    record_id: str
    damage: str
    healed_at: float
    source: str = "reserve"  # "reserve" or "scar" (healed without reserve)


class MortarStore:
    """A record wall with reactive reserve and a self-healing repair pass."""

    def __init__(self, reserve_ratio: float = 1.5) -> None:
        # Historic 1:1.5 lime:sand — the reserve holds 1.5x the wall's
        # records as reactive material.
        self.reserve_ratio = reserve_ratio
        self.wall: Dict[str, Dict] = {}  # live records
        self.reserve: Dict[str, Dict] = {}  # reactive reserve, write-once
        self.repairs: List[RepairEntry] = []
        self._reserve_spent = 0

    # -- pointing the wall ------------------------------------------------

    def lay(self, record_id: str, body: str, now: Optional[float] = None) -> Dict:
        """Lay a fresh record. The wall copy and its reserve shadow are sealed."""
        ts = now if now is not None else time.time()
        record = {
            "id": record_id,
            "body": body,
            "created_at": ts,
            "healed": False,
        }
        record["seal"] = _checksum(record)
        self.wall[record_id] = dict(record)
        # Reactive reserve: a sealed shadow, written once, never read by
        # normal gets — only the repair pass may touch it.
        self.reserve[record_id] = dict(record)
        self._repoint_reserve()
        return self.wall[record_id]

    def get(self, record_id: str) -> Dict:
        """Read from the wall. Never consults the reserve."""
        return self.wall[record_id]

    # -- cracking (for tests / weathering simulation) ---------------------

    def crack(self, record_id: str, mode: str = "tamper") -> None:
        """Simulate damage to the live wall copy only. The reserve is safe."""
        record = self.wall[record_id]
        if mode == "tamper":
            record["body"] = record["body"] + " [weathered]"
        elif mode == "truncate":
            record["body"] = record["body"][: max(1, len(record["body"]) // 2)]
        elif mode == "drop_field":
            del record["created_at"]
        else:
            raise ValueError(f"unknown crack mode {mode!r}")

    # -- inspection ---------------------------------------------------------

    def inspect(self, record_id: str) -> List[str]:
        """Return the list of cracks found in one wall record."""
        record = self.wall.get(record_id, {})
        cracks: List[str] = []
        for field_name in REQUIRED_FIELDS:
            if field_name not in record:
                cracks.append(f"missing-field:{field_name}")
        if "seal" in record and cracks == []:
            if record["seal"] != _checksum(record):
                cracks.append("seal-mismatch")
        return cracks

    def survey(self) -> Dict[str, List[str]]:
        """Sweep the whole wall; map record id -> cracks (empty if sound)."""
        return {rid: self.inspect(rid) for rid in self.wall}

    # -- repair pass ----------------------------------------------------------

    def repair(self, now: Optional[float] = None) -> List[RepairEntry]:
        """Heal every cracked record from the reactive reserve.

        Each heal consumes reserve material. If the reserve shadow for a
        record is itself gone (reserve exceeded its ratio), the record is
        scarred — marked healed-without-reserve — rather than silently
        invented.
        """
        ts = now if now is not None else time.time()
        healed: List[RepairEntry] = []
        for record_id, cracks in self.survey().items():
            if not cracks:
                continue
            damage = ",".join(cracks)
            shadow = self.reserve.get(record_id)
            if shadow is not None:
                self.wall[record_id] = dict(shadow)
                self.wall[record_id]["healed"] = True
                self._reserve_spent += 1
                entry = RepairEntry(record_id, damage, ts, source="reserve")
            else:
                self.wall[record_id]["healed"] = True
                entry = RepairEntry(record_id, damage, ts, source="scar")
            self.repairs.append(entry)
            healed.append(entry)
        return healed

    # -- reserve bookkeeping ----------------------------------------------------

    def reserve_capacity(self) -> int:
        """How many reserve records the current wall size may hold."""
        return int(len(self.wall) * self.reserve_ratio)

    def _repoint_reserve(self) -> None:
        """Keep the reserve within ratio: oldest-set shadows go first.

        The reserve is repointed (trimmed) only by inserting in id order;
        in practice new records land after old, so this trims the eldest
        shadows when the wall outgrows its ratio.
        """
        capacity = self.reserve_capacity()
        ids = sorted(self.reserve)
        for stale_id in ids[: max(0, len(ids) - capacity)]:
            del self.reserve[stale_id]

    def reserve_status(self) -> Dict:
        return {
            "shadows": len(self.reserve),
            "capacity": self.reserve_capacity(),
            "spent": self._reserve_spent,
        }
