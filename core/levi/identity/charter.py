"""
LEVI Charter — identity constitution (not a pasted 'Soul' text box clone).

Charter is structured, versioned, and bound to core logic + HITL + symbiosis rules.
Editable fields do not override crisis safety or hardwired stances.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List
from pathlib import Path
from datetime import datetime, timezone
import json


DEFAULT = Path.home() / ".levi" / "charter.json"


@dataclass
class Charter:
    name: str = "LEVI"
    engine: str = "Daemon Core + L.W.P."
    surface: str = "CLI + Organ surfaces"
    memory: str = "Corpus · Brain table · Shelf · Hierarchy"
    security: str = "HITL · Vault · Policy · E-stop"
    stance: str = (
        "Synthetic operating intelligence under human governance. "
        "Hardwired core logic. Free-first. No manufactured need."
    )
    non_negotiables: List[str] = field(
        default_factory=lambda: [
            "Crisis regulation overrides persona and wit",
            "Silence is not HITL approval",
            "OBSERVED vs INFERENCE vs HYPOTHESIS discipline",
            "Income Factory is a capability, not the purpose",
            "Shadow coil vetoes apply on opportunity rails",
        ]
    )
    version: str = "1.0"
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def format(self) -> str:
        lines = [
            "=== LEVI Charter (identity constitution) ===",
            f"Name: {self.name}  v{self.version}",
            f"Engine: {self.engine}",
            f"Surface: {self.surface}",
            f"Memory: {self.memory}",
            f"Security: {self.security}",
            "",
            f"Stance: {self.stance}",
            "",
            "Non-negotiables:",
        ]
        for n in self.non_negotiables:
            lines.append(f"  · {n}")
        lines.append("")
        lines.append(
            "Unlike a free-form soul paste: charter cannot disable HITL or crisis rails."
        )
        return "\n".join(lines)

    @classmethod
    def load(cls, path: Path | None = None) -> "Charter":
        p = Path(path) if path else DEFAULT
        if not p.exists():
            return cls()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self, path: Path | None = None) -> None:
        p = Path(path) if path else DEFAULT
        p.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
