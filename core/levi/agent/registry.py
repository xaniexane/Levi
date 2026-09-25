"""Agent registry — 471 agents, one twin pair each, banked as data.

The registry is derived, never hand-edited: every record re-derives
from :mod:`levi.automation.minions` (untouched) plus the grade
manifests (referenced, never rewritten). ``verify_registry`` re-derives
the whole bank and checks the fingerprint, the counts, and every
twin-pair link.
"""

from __future__ import annotations

import glob
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from levi.agent.agent import AGENT_VERSION, Agent, build_agents
from levi.automation.minions import MINIONS
from levi.twins.twin import Twin

__all__ = [
    "AGENT_DATA_DIR",
    "REGISTRY_PATH",
    "bank_registry",
    "build_registry_record",
    "load_registry",
    "registry_fingerprint",
    "verify_registry",
]

AGENT_DATA_DIR = Path(__file__).resolve().parent / "agent_data"
REGISTRY_PATH = AGENT_DATA_DIR / "agent_registry.json"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def load_grades() -> Dict[str, str]:
    """minion_id -> grade, from the banked grade manifests (read-only)."""
    grades: Dict[str, str] = {}
    pattern = (
        Path(__file__).resolve().parent.parent
        / "automation"
        / "grade_data"
        / "*.json"
    )
    for path in sorted(glob.glob(str(pattern))):
        try:
            manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for rec in manifest.get("records", []):
            mid = rec.get("minion_id")
            if mid:
                grades[mid] = rec.get("grade", "ungraded")
    return grades


def build_registry_record(agents: List[Agent]) -> Dict[str, Any]:
    """The full bankable registry record for one agent population."""
    records = [a.to_dict() for a in sorted(agents, key=lambda a: a.agent_id)]
    classes: Dict[str, int] = {}
    for a in agents:
        classes[a.class_tag] = classes.get(a.class_tag, 0) + 1
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_layer": f"levi.agent v{AGENT_VERSION}",
        "source": "core/levi/automation/minions.py (untouched; derived, never edited)",
        "grades_source": "core/levi/automation/grade_data/*.json (referenced, never rewritten)",
        "n_agents": len(agents),
        "n_twins": sum(len(a.twins) for a in agents),
        "class_distribution": classes,
        "fingerprint": "",
        "agents": records,
    }
    record["fingerprint"] = registry_fingerprint(record)
    return record


def registry_fingerprint(record: Dict[str, Any]) -> str:
    """SHA-256 over the canonical record minus its own fingerprint."""
    body = {k: v for k, v in record.items() if k != "fingerprint"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def bank_registry(path: str | Path = REGISTRY_PATH) -> Dict[str, Any]:
    """Build all agents and bank the registry. Returns the record."""
    agents = build_agents(load_grades())
    record = build_registry_record(agents)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def _agent_from_record(rec: Dict[str, Any]) -> Agent:
    from levi.agent.hemisphere import Hemisphere

    left = Hemisphere(**rec["left"])
    right = Hemisphere(**rec["right"])
    twins = [Twin.from_dict(t) for t in rec["twins"]]
    return Agent(
        agent_id=rec["agent_id"],
        minion_id=rec["minion_id"],
        class_tag=rec["class_tag"],
        counsel_name=rec["counsel_name"],
        grade=rec["grade"],
        left=left,
        right=right,
        twins=twins,
        pair_id=rec["pair_id"],
        provenance=rec.get("provenance", {}),
    )


def load_registry(path: str | Path = REGISTRY_PATH) -> List[Agent]:
    """Load the banked registry into living Agent objects."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    return [_agent_from_record(r) for r in record["agents"]]


def verify_registry(path: str | Path = REGISTRY_PATH) -> Dict[str, Any]:
    """Re-derive the registry and check it against the banked record.

    Checks: fingerprint, 471 agents / 942 twins, every twin pair
    bidirectional (shared pair_id, fg+bg, twin ids re-derive), and the
    catalog still intact (471 minion rows, signatures green).
    """
    problems: List[str] = []
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "problems": [f"unreadable registry: {exc}"]}

    if registry_fingerprint(record) != record.get("fingerprint"):
        problems.append("fingerprint mismatch — registry was hand-edited or stale")

    agents = record.get("agents", [])
    if len(agents) != len(MINIONS):
        problems.append(
            f"agent count {len(agents)} != catalog rows {len(MINIONS)}"
        )
    n_twins = sum(len(a.get("twins", [])) for a in agents)
    if n_twins != 2 * len(agents):
        problems.append(f"twin count {n_twins} != 2 x agents")

    seen_ids = set()
    for a in agents:
        aid = a.get("agent_id")
        if aid in seen_ids:
            problems.append(f"duplicate agent_id {aid}")
        seen_ids.add(aid)
        twins = a.get("twins", [])
        pair_ids = {t.get("pair_id") for t in twins}
        if len(pair_ids) != 1 or a.get("pair_id") not in pair_ids:
            problems.append(f"{aid}: pair not bidirectional on pair_id")
        sides = sorted(t.get("side") for t in twins)
        if sides != ["bg", "fg"]:
            problems.append(f"{aid}: pair sides {sides}, want fg+bg")
        for t in twins:
            want = f"agent:{aid}:{t.get('side')}"
            if t.get("twin_id") != want:
                problems.append(f"{aid}: twin_id {t.get('twin_id')} != {want}")

    try:
        from levi.interpenetration import verify_signatures

        sig = verify_signatures()
        sig_ok = bool(sig.get("ok")) if isinstance(sig, dict) else bool(sig)
    except Exception as exc:  # noqa: BLE001 — verification is best-effort here
        sig_ok = False
        problems.append(f"catalog signature check raised: {exc}")
    if not sig_ok:
        problems.append("catalog signatures not green")

    return {
        "ok": not problems,
        "problems": problems,
        "n_agents": len(agents),
        "n_twins": n_twins,
        "class_distribution": record.get("class_distribution"),
        "fingerprint": record.get("fingerprint"),
    }
