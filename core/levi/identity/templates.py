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


# Template dirs are package data (static at runtime); cache the parsed
# list keyed by an mtime fingerprint so get_template() doesn't re-parse
# every JSON file on every call.
_templates_cache: Dict[str, tuple] = {}


def _fingerprint(root: Path) -> tuple:
    try:
        return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in root.glob("*.json")))
    except OSError:
        return ()


def list_templates() -> List[Dict[str, Any]]:
    root = _root()
    key = str(root)
    fp = _fingerprint(root)
    cached = _templates_cache.get(key)
    if cached is not None and cached[0] == fp:
        return [dict(t) for t in cached[1]]
    out = []
    if root.exists():
        for p in sorted(root.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    d["_path"] = str(p)
                    out.append(d)
            except (OSError, ValueError):
                continue
    _templates_cache[key] = (fp, out)
    return [dict(t) for t in out]


def get_template(tid: str) -> Optional[Dict[str, Any]]:
    if not isinstance(tid, str) or not tid.strip():
        return None
    want = tid.strip().lower()
    for t in list_templates():
        tid_val = t.get("id")
        name_val = t.get("name")
        if (isinstance(tid_val, str) and tid_val.lower() == want) or (
            isinstance(name_val, str) and name_val.lower() == want
        ):
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
