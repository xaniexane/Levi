"""Template loader — free asset flywheel seeds."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

# templates live next to package or in levi_core/templates
_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "templates",
    Path(__file__).resolve().parents[3] / "templates",
]


def _root() -> Path:
    for c in _CANDIDATES:
        if c.is_dir():
            return c
    return _CANDIDATES[0]


def list_templates() -> List[Dict[str, Any]]:
    root = _root()
    out = []
    if not root.exists():
        return out
    for p in sorted(root.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["_path"] = str(p)
            out.append(d)
        except Exception:
            continue
    return out


def get_template(tid: str) -> Optional[Dict[str, Any]]:
    for t in list_templates():
        if t.get("id") == tid or t.get("name", "").lower() == tid.lower():
            return t
    return None


def apply_template(tid: str) -> str:
    """Run template NL through appropriate skill."""
    t = get_template(tid)
    if not t:
        return f"Unknown template: {tid}. Try: levi templates"
    nl = t.get("nl") or ""
    kind = t.get("kind") or "factory"
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    if kind == "factory":
        return str(reg.invoke("factory_create", {"text": nl}))
    if kind == "automation":
        return str(reg.invoke("automation_create", {"text": nl}))
    if kind == "story":
        return str(reg.invoke("story_create", {"text": nl}))
    return str(reg.invoke("compile_ir", {"text": nl}))
