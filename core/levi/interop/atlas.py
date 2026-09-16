"""The LEVI capability atlas — one stable contract for the organism's map.

This is the stable contract other workers (CLI, docs, UX) depend on:

- :func:`export_atlas` -> a dict with everything: the flat module list
  (kept — existing consumers may rely on it), capabilities, the
  requires-graph, CLI reachability, and the modules grouped under their
  *warehouses* (see :mod:`levi.interop.warehouses`), plus
  ``generated_at`` and ``levi_version``.
- :func:`write_atlas` -> writes that dict as JSON to a path.

The atlas is generated from :data:`levi.interop.manifest.DECLARATIONS`
(the deny-closed source of truth) — it never hand-lists modules, so it
can't drift from the manifest.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.interop.manifest import DECLARATIONS
from levi.interop.registry import Registry, RegistryError
from levi.interop.warehouses import CLI_COMMANDS, WAREHOUSES, list_warehouses

__all__ = ["export_atlas", "write_atlas", "atlas_modules"]


def _levi_version() -> str:
    try:
        import levi

        return str(getattr(levi, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def _validate() -> Registry:
    """Load the static manifest into a fresh registry, deny-closed."""
    reg = Registry()
    for name, decl in DECLARATIONS.items():
        reg.register(name, provides=decl["provides"], requires=decl["requires"])
    reg.check_all()
    return reg


def atlas_modules() -> Dict[str, Dict[str, Any]]:
    """Flat module list: every declared module with its provides/requires
    and CLI reachability. Deny-closed: raises RegistryError when the
    manifest is invalid."""
    _validate()  # deny-closed: unknown requires targets rejected here
    modules: Dict[str, Dict[str, Any]] = {}
    for name in sorted(DECLARATIONS):
        decl = DECLARATIONS[name]
        modules[name] = {
            "provides": list(decl.get("provides", [])),
            "requires": list(decl.get("requires", [])),
            "cli": list(CLI_COMMANDS.get(name, [])),
        }
    return modules


def _requires_graph() -> Dict[str, List[str]]:
    return {
        name: list(DECLARATIONS[name].get("requires", []))
        for name in sorted(DECLARATIONS)
    }


def _warehouses_grouping() -> Dict[str, Dict[str, Any]]:
    """Modules grouped under their warehouses, each with its real
    inventory manifest."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for wh in list_warehouses():  # inventory_count is counted, never estimated
        name = wh["name"]
        browse = _browse_light(name)
        grouped[name] = browse
    return grouped


def _browse_light(name: str) -> Dict[str, Any]:
    from levi.interop.warehouses import browse_warehouse

    return browse_warehouse(name)


def export_atlas() -> Dict[str, Any]:
    """The full capability atlas.

    Keys:

    - ``modules``: flat module map (provides / requires / cli) — kept for
      existing consumers.
    - ``capabilities``: sorted list of every declared capability id.
    - ``requires_graph``: module -> [required modules].
    - ``warehouses``: modules grouped under named warehouses, each with
      its inventory manifest (real counts).
    - ``generated_at``: UTC ISO timestamp.
    - ``levi_version``: the kernel version string.
    """
    modules = atlas_modules()
    capabilities = sorted(
        {cap for m in modules.values() for cap in m["provides"]}
    )
    return {
        "modules": modules,
        "capabilities": capabilities,
        "requires_graph": _requires_graph(),
        "warehouses": _warehouses_grouping(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "levi_version": _levi_version(),
    }


def write_atlas(path: Optional[Path] = None) -> Path:
    """Write :func:`export_atlas` as JSON. Default: ``~/.levi/atlas.json``.

    Returns the path written.
    """
    target = Path(path) if path else (Path.home() / ".levi" / "atlas.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(export_atlas(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return target
