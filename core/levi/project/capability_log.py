"""
Capability log — evidence for future LEVI skills (pre-MVP).

Every meaningful task records: what ran, tools, human required?, failure modes,
future skill candidate. Derived from real work, not fabricated capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid


DEFAULT_PATH = Path.home() / ".levi" / "capability_log.json"


@dataclass
class CapEntry:
    id: str
    task: str
    result: str = ""  # completed | partial | failed | blocked
    tools: List[str] = field(default_factory=list)
    inputs: str = ""
    output_summary: str = ""
    complexity: str = "medium"  # low | medium | high
    automatable: str = "partial"  # yes | partial | no
    human_required: bool = False
    external_required: bool = False
    failure_modes: str = ""
    safety: str = ""
    reusable: bool = True
    future_skill: str = ""
    phase: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CapEntry":
        return cls(
            id=d.get("id") or str(uuid.uuid4())[:8],
            task=d.get("task") or "",
            result=d.get("result") or "",
            tools=list(d.get("tools") or []),
            inputs=d.get("inputs") or "",
            output_summary=d.get("output_summary") or "",
            complexity=d.get("complexity") or "medium",
            automatable=d.get("automatable") or "partial",
            human_required=bool(d.get("human_required", False)),
            external_required=bool(d.get("external_required", False)),
            failure_modes=d.get("failure_modes") or "",
            safety=d.get("safety") or "",
            reusable=bool(d.get("reusable", True)),
            future_skill=d.get("future_skill") or "",
            phase=d.get("phase") or "",
            created_at=d.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )


class CapabilityLog:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self.entries: List[CapEntry] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = [CapEntry.from_dict(x) for x in (raw.get("entries") or [])]
        except Exception:
            self.entries = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [e.to_dict() for e in self.entries[-500:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def log(
        self,
        task: str,
        result: str = "completed",
        tools: Optional[List[str]] = None,
        inputs: str = "",
        output_summary: str = "",
        complexity: str = "medium",
        automatable: str = "partial",
        human_required: bool = False,
        external_required: bool = False,
        failure_modes: str = "",
        safety: str = "",
        reusable: bool = True,
        future_skill: str = "",
        phase: str = "",
    ) -> CapEntry:
        e = CapEntry(
            id=str(uuid.uuid4())[:8],
            task=task,
            result=result,
            tools=tools or [],
            inputs=inputs,
            output_summary=output_summary,
            complexity=complexity,
            automatable=automatable,
            human_required=human_required,
            external_required=external_required,
            failure_modes=failure_modes,
            safety=safety,
            reusable=reusable,
            future_skill=future_skill,
            phase=phase,
        )
        self.entries.append(e)
        self._persist()
        return e

    def list_entries(self, limit: int = 20) -> List[CapEntry]:
        return list(reversed(self.entries[-limit:]))

    def skill_candidates(self) -> List[str]:
        seen = []
        for e in self.entries:
            if e.future_skill and e.future_skill not in seen:
                seen.append(e.future_skill)
        return seen

    def format(self, limit: int = 15) -> str:
        lines = ["=== LEVI Capability Log (pre-MVP evidence) ===", ""]
        if not self.entries:
            lines.append("No entries yet. Log tasks as you run phases.")
            return "\n".join(lines)
        for e in self.list_entries(limit):
            lines.append(f"[{e.id}] {e.task}")
            lines.append(
                f"  result={e.result}  auto={e.automatable}  human={e.human_required}  "
                f"skill={e.future_skill or '—'}"
            )
            if e.output_summary:
                lines.append(f"  out: {e.output_summary[:120]}")
        cands = self.skill_candidates()
        if cands:
            lines.append("")
            lines.append("Future skill candidates: " + ", ".join(cands[:20]))
        return "\n".join(lines)
