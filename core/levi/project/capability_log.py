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
import os
import uuid


DEFAULT_PATH = Path.home() / ".levi" / "capability_log.json"

_RESULT_VALUES = ("completed", "partial", "failed", "blocked")
_COMPLEXITY_VALUES = ("low", "medium", "high")
_AUTOMATABLE_VALUES = ("yes", "partial", "no")


def _clamp_limit(limit: int, default: int = 20) -> int:
    """Positive-int guard for display limits (never unbounded)."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return default
    return min(limit, 1000)


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
        # Atomic + owner-only: log entries describe the user's real work.
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp, self.path)

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
        # The log is evidence for future skills — garbage in, garbage out.
        if not isinstance(task, str) or not task.strip():
            raise ValueError("CapabilityLog.log: task must be a non-empty string")
        if result not in _RESULT_VALUES:
            raise ValueError(
                "CapabilityLog.log: result must be one of %s, got %r"
                % (", ".join(_RESULT_VALUES), result)
            )
        if complexity not in _COMPLEXITY_VALUES:
            raise ValueError(
                "CapabilityLog.log: complexity must be one of %s, got %r"
                % (", ".join(_COMPLEXITY_VALUES), complexity)
            )
        if automatable not in _AUTOMATABLE_VALUES:
            raise ValueError(
                "CapabilityLog.log: automatable must be one of %s, got %r"
                % (", ".join(_AUTOMATABLE_VALUES), automatable)
            )
        if tools is not None and (
            not isinstance(tools, (list, tuple))
            or any(not isinstance(t, str) for t in tools)
        ):
            raise ValueError("CapabilityLog.log: tools must be a list of str (or None)")
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
        limit = _clamp_limit(limit)
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
