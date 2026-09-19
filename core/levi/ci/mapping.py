"""Agent → class mapping for the CI counsels.

Keeper's canon (2026-09-18): the minions are actually AGENTS — ai and si
xi — each a twin pair (left/right brain). The living entity is the agent;
``Minion`` remains strictly the frozen intake-record dataclass.

So this mapping addresses agent-twins, not bare rows: one agent per
catalog row id, classed AI / SI / XI. The class is derived
deterministically from the frozen intake record — the record is read,
never edited (``minions.py`` stays verbatim under its Echo x Mandella
signatures). The banked map lives at
``core/levi/automation/grade_data/ci_class_map.json``.

Derivation (data-grounded, in order):
  1. ``intake`` — rows still capped at intake grade (incomplete); no counsel.
  2. ``SI`` — agents whose intake record carries the Wave-B full-signature
     lineage (``Signature:`` in notes): dynasty-native agents whose rites
     run through Echo, Mandella, REIM, and RIEM. SICI reasons in kind.
  3. ``XI`` — trivial-turn bulk: light-gate routine agents (NOTIFICATION,
     ACKNOWLEDGE gates). XICI is the nano-fast counsel for this overflow.
  4. ``AI`` — everything else: judgment-grade gates (dialog, approval,
     edit-approve, confirm) where a generalist advisory counsel earns its
     keep. AICI.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from levi.automation import hitl
from levi.automation.minions import MINIONS, Minion

#: Classes the counsels serve. "intake" = no counsel yet (capped rows).
CLASSES: Tuple[str, ...] = ("AI", "SI", "XI", "intake")

#: Counsel per class.
COUNSEL_FOR_CLASS: Dict[str, str] = {"AI": "AICI", "SI": "SICI", "XI": "XICI"}

#: Gates light enough to count as trivial-turn bulk (nano-bit territory).
_XI_GATES = frozenset(
    {hitl.GateKind.NOTIFICATION.value, hitl.GateKind.ACKNOWLEDGE.value}
)

#: Wave-B signature marker in a minion's notes: dynasty-native lineage.
_SIGNATURE_MARKER = "Signature:"


def class_for_minion(minion: Minion) -> str:
    """Derive the counsel class for one agent from its frozen intake record."""
    if getattr(minion, "incomplete", False):
        return "intake"
    notes = minion.notes or ""
    if _SIGNATURE_MARKER in notes:
        return "SI"
    gate = hitl.gate_kind_for(minion.hitl_type)
    if gate.value in _XI_GATES:
        return "XI"
    return "AI"


def class_for_agent(agent_id: str) -> str:
    """Derive the counsel class for one agent-twin by agent id.

    The agent id is the catalog row id — the stable identity shared with
    the agent twin-pair layer on the twins/ machinery.
    """
    for m in MINIONS:
        if m.id == agent_id:
            return class_for_minion(m)
    raise KeyError(f"unknown agent id: {agent_id}")


def agent_twins_in_class(class_tag: str) -> List[str]:
    """Agent ids serving under one class counsel, sorted."""
    return sorted(m.id for m in MINIONS if class_for_minion(m) == class_tag)


def counsel_for_class(class_tag: str) -> str:
    """Name the counsel serving a class ('' for intake — no counsel)."""
    return COUNSEL_FOR_CLASS.get(class_tag, "")


def build_class_map() -> Dict[str, str]:
    """Map every minion id to its class. Deterministic, id-sorted."""
    return {m.id: class_for_minion(m) for m in sorted(MINIONS, key=lambda m: m.id)}


def class_distribution(class_map: Dict[str, str]) -> Dict[str, int]:
    """Count minions per class."""
    dist: Dict[str, int] = {c: 0 for c in CLASSES}
    for cls in class_map.values():
        dist[cls] = dist.get(cls, 0) + 1
    return dist


def minions_in_class(class_tag: str) -> List[Minion]:
    """All minions serving under one class counsel."""
    return [m for m in MINIONS if class_for_minion(m) == class_tag]


def _canonical(class_map: Dict[str, str]) -> str:
    return json.dumps(class_map, sort_keys=True, separators=(",", ":"))


def map_fingerprint(class_map: Dict[str, str]) -> str:
    """SHA-256 over the canonical map — the map's integrity seal."""
    return hashlib.sha256(_canonical(class_map).encode("utf-8")).hexdigest()


def bank_class_map(path: str | Path) -> Dict[str, object]:
    """Write the class map to disk with its fingerprint. Returns the record."""
    class_map = build_class_map()
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "core/levi/automation/minions.py (untouched; derived, never edited)",
        "ontology": (
            "agent-twins (keeper canon 2026-09-18): one agent per row id, "
            "classed AI/SI/XI, each a left/right-brain twin pair; Minion is "
            "strictly the frozen intake-record dataclass"
        ),
        "rule": "intake -> SI(signature) -> XI(light gates) -> AI(rest)",
        "counsels": COUNSEL_FOR_CLASS,
        "distribution": class_distribution(class_map),
        "fingerprint": map_fingerprint(class_map),
        "classes": class_map,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def verify_banked_map(path: str | Path) -> bool:
    """Re-derive the map and check it against the banked fingerprint."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    return map_fingerprint(build_class_map()) == record["fingerprint"]
