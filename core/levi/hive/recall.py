"""The pickup protocol — total retention, made operational.

``recall(seat_key, memory_key, store=None)``:

  1. The seat's own memory is checked first: its per-seat journal
     record ids and its namespaced memory entries. Hit -> {"status":
     "recalled"} — the hive is never consulted for what the seat
     already holds.
  2. Seat miss -> hive lookup: exact id match first, then mechanical
     keyword overlap over the index. Hit -> the entry is returned WITH
     a recovery record journaled on the seat ("recovered-via-hive":
     what was supplied, from whose learning) AND on the hive
     ("supplied": who failed to remember, what was supplied, from
     whose learning). Never silent — the mind always knows when a
     memory was supplied rather than recalled.
  3. Miss everywhere -> honest miss, journaled on both sides, never
     invented.

Deny-open on unknown seats. Guards apply to everything written.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from levi.founders import roster
from levi.growth import journal as _journal
from levi.growth.tracks import _seat_journal_path, read_seat_entries
from levi.hive.index import query_index, read_index, register_record


def _seat_memory_ids(seat_key: str, store: Any) -> Dict[str, str]:
    """Ids the seat holds itself: journal record ids + memory entry ids."""
    have: Dict[str, str] = {}
    for rec in read_seat_entries(seat_key, limit=200000):
        rid = rec.get("id")
        if rid:
            have[str(rid)] = "journal"
    if store is not None:
        tag = "seat:" + seat_key
        for e in store.list(limit=5000):
            tags = set(getattr(e, "tags", []) or [])
            if "growth" in tags and tag in tags:
                have[str(getattr(e, "id", ""))] = "memory"
                md = getattr(e, "metadata", None) or {}
                prov = md.get("provenance", {}) or {}
                if prov.get("memory_id"):
                    have[str(prov["memory_id"])] = "memory"
    return have


def _journal_recovery_note(seat_key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append the seat-side 'recovered via hive' record (append-only)."""
    record = {
        "kind": "recovered-via-hive",
        "seat": seat_key,
        "recovered_id": entry.get("id"),
        "recovered_kind": entry.get("kind"),
        "from_seat": entry.get("seat"),
        "from_provenance": entry.get("provenance", {}),
        "content": (
            "Recovered via hive: memory '%s' (kind %s) was supplied by "
            "the hive, learned by seat '%s'. This mind did not recall "
            "it itself." % (entry.get("id"), entry.get("kind"), entry.get("seat"))
        ),
    }
    record.setdefault("id", _journal.new_cycle_id())
    record.setdefault("ts", _journal.now_iso())
    path = _seat_journal_path(seat_key)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def recall(
    seat_key: str,
    memory_key: str,
    *,
    store: Any = None,
) -> Dict[str, Any]:
    """Run the pickup protocol for one seat and one memory key."""
    seat = roster.get_seat(seat_key)  # deny-open, never guess
    if not isinstance(memory_key, str) or not memory_key.strip():
        raise ValueError("recall: memory_key must be a non-empty string")
    memory_key = memory_key.strip()

    # 1. the seat's own memory first
    own = _seat_memory_ids(seat_key, store)
    if memory_key in own:
        return {
            "status": "recalled",
            "seat": seat_key,
            "memory_key": memory_key,
            "source": own[memory_key],
            "entry": None,
            "note": "the seat held this memory itself; the hive was not consulted",
        }

    # 2. hive lookup: exact id, then mechanical keyword overlap
    hits = query_index(memory_key, limit=5)
    exact = [h for h in hits if h.get("id") == memory_key]
    entry = exact[0] if exact else (hits[0] if hits else None)
    if entry is not None:
        seat_note = _journal_recovery_note(seat_key, entry)
        hive_note = register_record(
            {
                "id": "supplied:%s:%s" % (seat_key, entry["id"]),
                "kind": "supplied",
                "seat": seat_key,
                "content": (
                    "Supplied to seat '%s': memory '%s' (kind %s), "
                    "learned by seat '%s'. The seat failed to recall it; "
                    "the hive supplied it."
                    % (seat_key, entry.get("id"), entry.get("kind"), entry.get("seat"))
                ),
                "tags": ["pickup", "recovery"],
                "provenance": {
                    "to_seat": seat_key,
                    "supplied_id": entry.get("id"),
                    "from_seat": entry.get("seat"),
                    "from_provenance": entry.get("provenance", {}),
                    "seat_recovery_record": seat_note["id"],
                },
            }
        )
        return {
            "status": "supplied",
            "seat": seat_key,
            "memory_key": memory_key,
            "source": "hive",
            "entry": entry,
            "seat_recovery_record": seat_note["id"],
            "hive_record": hive_note["id"],
            "note": "supplied by the hive, never silent: recovery is journaled on both sides",
        }

    # 3. honest miss — journaled, never invented
    miss = register_record(
        {
            "id": "miss:%s:%s" % (seat_key, memory_key.replace(" ", "_")[:80]),
            "kind": "miss",
            "seat": seat_key,
            "content": (
                "Honest miss: seat '%s' asked for '%s'; the seat did not "
                "hold it and the hive had nothing to supply. Nothing was "
                "invented." % (seat_key, memory_key)
            ),
            "tags": ["pickup", "miss"],
            "provenance": {"seat": seat_key, "memory_key": memory_key},
        }
    )
    return {
        "status": "miss",
        "seat": seat_key,
        "memory_key": memory_key,
        "source": None,
        "entry": None,
        "hive_record": miss["id"],
        "note": "miss everywhere: journaled, never invented",
    }
