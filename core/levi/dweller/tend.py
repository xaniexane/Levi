"""The Dweller's tending rites — what it does for the waiting.

Rites:

- ``compost_review``: break failure records down through REIM, lay them
  in the compost heap, and surface RIEM genome candidates. Review is
  data, never application: REIM breaks down, RIEM proposes, a human or
  Omega decides.
- ``redrive_dead_letter``: send a dead letter back through the Nexus —
  ONLY through the permission gate. A denied gate ends the rite
  cleanly; the in-between never routes around the human.
- ``release_dead_letter``: let a dead letter go with a receipt. Nothing
  leaves purgatory silently.
- ``unborn_watch``: report what each unborn concept has and what it
  still needs to be born.

Every rite ends with a receipt, recorded in the tending log.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.automation.hitl import Gate, GateKind, GateRequest

from .purgatory import (
    levi_base,
    read_dead_letters,
    read_unborn,
    record_tending,
)


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _heap_path(base: Path) -> Path:
    return base / ".levi" / "dweller" / "compost.jsonl"


def compost_review(
    failure_records: List[Dict[str, Any]],
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tending rite: review failures into compost, surface genome
    candidates. Returns the rite's receipt."""
    from levi.organs.reim import compost_failure
    from levi.organs.riem import promote

    b = levi_base(base)
    heap = _heap_path(b)
    heap.parent.mkdir(parents=True, exist_ok=True)
    composted: List[Dict[str, Any]] = []
    for record in failure_records:
        compost = compost_failure(record)
        composted.append(compost)
        with heap.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(compost, sort_keys=True) + "\n")
    candidates = promote(composted)
    receipt = {
        "rite": "compost-review",
        "records_reviewed": len(failure_records),
        "composted": len(composted),
        "genome_candidates": len(candidates),
        "candidates": candidates,
        "note": ("review only — nothing applied; candidates await a human or Omega"),
        "ts": _utcnow(),
    }
    record_tending(b, "compost", "review", "compost-review", receipt)
    return receipt


def _dead_letter_by_index(base: Path, index: int) -> Dict[str, Any]:
    entries, status, note = read_dead_letters(base)
    if status != "live":
        raise KeyError("dead-letter store %s" % note)
    if not 0 <= index < len(entries):
        raise KeyError("no dead letter at index %d" % index)
    return entries[index]


def redrive_dead_letter(
    index: int,
    responder,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tending rite: re-drive a dead letter through the Nexus — only
    through the permission gate. Denial ends the rite cleanly."""
    from levi.nexus.envelope import Envelope
    from levi.nexus.si.engine import NexusEngine

    b = levi_base(base)
    letter = _dead_letter_by_index(b, index)
    env_dict = letter.get("envelope", {}) or {}
    gate = Gate(
        GateRequest(
            minion_id="dweller",
            kind=GateKind.CONFIRM,
            prompt="re-drive dead letter %d (%s → %s)?"
            % (
                index,
                env_dict.get("from_organ", "?"),
                env_dict.get("to_organ", "?"),
            ),
            context={
                "realm": "dead-letters",
                "index": index,
                "reason": letter.get("reason", ""),
            },
        )
    )
    result = gate.resolve(responder)
    if not result.ok:
        receipt = {
            "rite": "re-drive",
            "index": index,
            "decision": "denied",
            "note": "gate denied — the letter stays in the in-between",
            "ts": _utcnow(),
        }
        record_tending(b, "dead-letters", str(index), "re-drive-denied", receipt)
        return receipt
    envelope = Envelope.from_dict(env_dict)
    engine = NexusEngine(home=b)
    route_receipt = engine.route(envelope)
    receipt = {
        "rite": "re-drive",
        "index": index,
        "decision": "redriven",
        "route": route_receipt.to_dict()
        if hasattr(route_receipt, "to_dict")
        else str(route_receipt),
        "gate_note": result.note,
        "ts": _utcnow(),
    }
    record_tending(b, "dead-letters", str(index), "re-drive", receipt)
    return receipt


def release_dead_letter(
    index: int,
    reason: str,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tending rite: release a dead letter — let it go, with a receipt."""
    b = levi_base(base)
    letter = _dead_letter_by_index(b, index)
    receipt = {
        "rite": "release",
        "index": index,
        "decision": "released",
        "reason": reason,
        "letter_reason": letter.get("reason", ""),
        "note": "released from purgatory with a receipt — nothing leaves silently",
        "ts": _utcnow(),
    }
    record_tending(b, "dead-letters", str(index), "release", receipt)
    return receipt


def unborn_watch(docs_path: Optional[Path] = None) -> Dict[str, Any]:
    """Tending rite: watch the unborn — report what each named-but-unbuilt
    concept has, and what it still needs to be born."""
    entries, status, note = read_unborn(docs_path)
    watch = []
    for entry in entries:
        notes = entry.get("notes", "")
        # What it has: anything the notes say exists; what it needs: a
        # build wave, since UNBORN means named but never built.
        watch.append(
            {
                "name": entry.get("name", "?"),
                "what": entry.get("what", ""),
                "has": notes if notes else "a name and a place in the lineage",
                "needs": (
                    "a build wave: working LEVI-native organ, tests, "
                    "interop wiring — nothing is born from a name alone"
                ),
            }
        )
    return {
        "rite": "unborn-watch",
        "status": status,
        "note": note,
        "unborn": watch,
        "ts": _utcnow(),
    }
