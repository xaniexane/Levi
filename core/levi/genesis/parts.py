"""Capability catalog for the genesis parts bin.

The parts bin is the 11-agent capability build under
``core/levi/dynasty/wave/`` (read-only; genesis never edits it). This module
parses those sources STATically with ``ast`` — no import, so heavy dynasty
dependencies never load at catalog time.

Eyes-only rule: dynasty-internal identifiers (agent proper names, Section 0
headers, provenance, playbook references) are INTERNAL-ONLY. The catalog
exposes them under ``internal`` keys for forge lineage only; every
user-facing surface (variant descriptions, README, docs) goes through
``public_traits()``, which carries only generic capability language and is
checked against ``levi.bot.persona.check_no_mask`` by the forge.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

FORM_NAME = "genesis.parts"

#: The 11 capability sources. Graft-companion files (<id>_grafts,
#: <id>_tools, ...) belong to the same agent; only the base module is
#: parsed — the graft suffixes are folded into the base lineage hash.
BASE_AGENTS = (
    "forgehand",
    "gamemaster",
    "herald",
    "keystone",
    "quartermaster",
    "schoolmaster",
    "shellwright",
    "starmaker",
    "threadweaver",
    "vaultkeeper",
    "veilwright",
)


def _wave_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "dynasty" / "wave"


def _graft_files(agent_id: str, wave_dir: Path) -> List[Path]:
    return sorted(wave_dir.glob(agent_id + "_*.py"))


def _extract_scalar(tree: ast.Module, attr: str) -> Optional[str]:
    """Pull a class-level ``attr = "..."`` string literal via AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == attr
                ):
                    val = stmt.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        return val.value
    return None


def _extract_str_list(tree: ast.Module, attr: str) -> List[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == attr
                ):
                    val = stmt.value
                    if isinstance(val, (ast.List, ast.Tuple)):
                        out = []
                        for elt in val.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                out.append(elt.value)
                        return out
    return []


def _sha256_of(paths: List[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()


def load_capability(agent_id: str) -> Dict[str, Any]:
    """Static profile of one capability source (internal record)."""
    wave = _wave_dir()
    base = wave / (agent_id + ".py")
    if not base.exists():
        raise KeyError("unknown capability source: %r" % agent_id)
    tree = ast.parse(base.read_text(encoding="utf-8"))
    lineage = [base] + _graft_files(agent_id, wave)
    return {
        "agent_id": agent_id,
        "display_name": _extract_scalar(tree, "display_name"),
        "owns": _extract_scalar(tree, "owns"),
        "first_milestone": _extract_scalar(tree, "first_milestone"),
        "specialties": _extract_str_list(tree, "specialties"),
        "lineage_hash": _sha256_of(lineage),
        "source_files": [p.name for p in lineage],
        # INTERNAL-ONLY: never render these on user-facing surfaces.
        "internal": {"graft_count": len(lineage) - 1},
    }


def list_capabilities() -> List[Dict[str, Any]]:
    """All 11 capability sources, in canonical order."""
    return [load_capability(a) for a in BASE_AGENTS]


def find_capability(agent_id: str) -> Dict[str, Any]:
    return load_capability(agent_id)


def catalog_receipt() -> Dict[str, Any]:
    """Hash-chain receipt over the whole parts bin (lineage only).

    Carries NO internal names — only the count and the binding hash —
    so it is safe to embed in buyer-facing manifests.
    """
    caps = list_capabilities()
    h = hashlib.sha256()
    for cap in caps:
        h.update(cap["agent_id"].encode("utf-8"))
        h.update(cap["lineage_hash"].encode("utf-8"))
    return {
        "form": FORM_NAME,
        "count": len(caps),
        "catalog_hash": h.hexdigest(),
    }
