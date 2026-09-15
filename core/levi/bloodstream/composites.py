"""Interpenetration — named composites with strictest-risk-ceiling inheritance.

Composition law: persona + skills + specialists + automations → named
composite → registerable. A composite inherits the STRICTEST (maximum)
risk ceiling of its parts:

- persona ............ risk 0 — a lens, never a security boundary
- skills ............. Skill.risk_level (0–4)
- specialists ........ Specialist.risk_ceiling
- automations ........ Automation.risk_ceiling

Composites are nameable, testable, reversible: register() validates every
part exists (fail fast), unregister() removes the name. The governor stage
of the bloodstream enforces the composite ceiling on the whole turn.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # registry types only; runtime stays duck-typed
    from levi.agent.specialists import SpecialistRegistry
    from levi.daemon.automation import AutomationRegistry
    from levi.skill.registry import SkillRegistry


@dataclass
class Composite:
    name: str
    description: str = ""
    persona_id: Optional[str] = None
    skill_ids: List[str] = field(default_factory=list)
    specialist_ids: List[str] = field(default_factory=list)
    automation_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Composite":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            persona_id=data.get("persona_id"),
            skill_ids=list(data.get("skill_ids", [])),
            specialist_ids=list(data.get("specialist_ids", [])),
            automation_ids=list(data.get("automation_ids", [])),
        )

    @classmethod
    def validated(cls, name: Any, data: Any) -> Optional["Composite"]:
        """Build from an untrusted persisted record.

        Returns None for malformed records (skipped, never aborting the
        whole load). String-id lists must be actual lists of strings —
        a bare string is rejected, not char-split.
        """
        if not isinstance(data, dict):
            return None
        if not isinstance(name, str) or not name:
            return None
        comp_name = data.get("name", name)
        if not isinstance(comp_name, str) or not comp_name:
            return None
        description = data.get("description", "")
        if not isinstance(description, str):
            return None
        persona_id = data.get("persona_id")
        if persona_id is not None and not isinstance(persona_id, str):
            return None
        id_lists = {}
        for key in ("skill_ids", "specialist_ids", "automation_ids"):
            ids = data.get(key, [])
            if not isinstance(ids, list) or any(
                not isinstance(i, str) for i in ids
            ):
                return None
            id_lists[key] = list(ids)
        return cls(
            name=comp_name,
            description=description,
            persona_id=persona_id,
            **id_lists,
        )


class CompositeRegistry:
    """Named composites, persisted as JSON. Reversible by design."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = (
            Path(data_dir) if data_dir else Path.home() / ".levi" / "bloodstream"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.data_dir / "composites.json"
        self._items: Dict[str, Composite] = {}
        self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return  # corrupt root: start empty rather than crash
        for name, data in raw.items():
            comp = Composite.validated(name, data)
            if comp is not None:
                self._items[comp.name] = comp
            # malformed records are skipped individually; the rest load

    def _persist(self) -> None:
        try:
            payload = json.dumps(
                {n: c.to_dict() for n, c in self._items.items()}, indent=2
            )
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(self._path)
        except OSError:
            pass

    # -- registry ---------------------------------------------------------
    def register(
        self,
        composite: Composite,
        *,
        skills: Optional["SkillRegistry"] = None,
        specialists: Optional["SpecialistRegistry"] = None,
        automations: Optional["AutomationRegistry"] = None,
    ) -> Composite:
        """Name a composite. Validates every part exists — fail fast, never
        a dangling reference. Returns the composite (reversible via unregister)."""
        if not isinstance(composite, Composite):
            raise ValueError(
                f"register() needs a Composite, got {type(composite).__name__}"
            )
        if not isinstance(composite.name, str) or not composite.name.strip():
            raise ValueError("composite needs a non-empty string name")
        for key in ("skill_ids", "specialist_ids", "automation_ids"):
            ids = getattr(composite, key)
            if not isinstance(ids, list) or any(
                not isinstance(i, str) or not i for i in ids
            ):
                raise ValueError(
                    f"composite {composite.name!r}: {key} must be a list of "
                    "non-empty string ids"
                )
        missing = self._missing_parts(composite, skills, specialists, automations)
        if missing:
            raise ValueError(
                f"composite {composite.name!r} references unknown parts: {missing}"
            )
        # Personas are lenses: unknown persona ids are allowed but recorded.
        self._items[composite.name] = composite
        self._persist()
        return composite

    def unregister(self, name: str) -> bool:
        if not isinstance(name, str):
            return False
        if name in self._items:
            del self._items[name]
            self._persist()
            return True
        return False

    def get(self, name: str) -> Optional[Composite]:
        if not isinstance(name, str):
            return None
        return self._items.get(name)

    def list(self) -> List[Composite]:
        return list(self._items.values())

    # -- risk ceiling ------------------------------------------------------
    def risk_ceiling(
        self,
        composite: Composite,
        *,
        skills: Optional["SkillRegistry"] = None,
        specialists: Optional["SpecialistRegistry"] = None,
        automations: Optional["AutomationRegistry"] = None,
    ) -> int:
        """Strictest (maximum) risk ceiling across all parts. Personas
        contribute 0 — they are communication lenses, not authority."""
        ceiling = 0
        if skills is not None:
            for sid in composite.skill_ids:
                s = skills.get(sid)
                if s is not None:
                    ceiling = max(ceiling, int(getattr(s, "risk_level", 0)))
        if specialists is not None:
            for sid in composite.specialist_ids:
                s = specialists.get(sid)
                if s is not None:
                    ceiling = max(ceiling, int(getattr(s, "risk_ceiling", 0)))
        if automations is not None:
            for aid in composite.automation_ids:
                a = automations.get(aid)
                if a is not None:
                    ceiling = max(ceiling, int(getattr(a, "risk_ceiling", 0)))
        return ceiling

    def _missing_parts(
        self,
        composite: Composite,
        skills: Optional["SkillRegistry"],
        specialists: Optional["SpecialistRegistry"],
        automations: Optional["AutomationRegistry"],
    ) -> List[str]:
        missing: List[str] = []
        if skills is not None:
            missing += [
                f"skill:{s}" for s in composite.skill_ids if skills.get(s) is None
            ]
        if specialists is not None:
            missing += [
                f"specialist:{s}"
                for s in composite.specialist_ids
                if specialists.get(s) is None
            ]
        if automations is not None:
            missing += [
                f"automation:{a}"
                for a in composite.automation_ids
                if automations.get(a) is None
            ]
        return missing
