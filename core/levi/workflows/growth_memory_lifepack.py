"""growth-memory-lifepack: growth cycle -> memory consolidation -> lifepack export.

Runs one real growth cycle (:py:func:`levi.growth.cycle.run_cycle`) against a
hermetic home, reports the consolidation counts the cycle produced, then
builds a life-pack export (:py:func:`levi.lifepack.pack.export_pack`) and
validates it.

The cycle runs with ``use_model=False`` by default so the workflow is fully
offline; pass ``use_model=True`` to allow a model-assisted reflection when a
provider is reachable. ``dry_run=True`` previews everything without writing
memory, journal, or pack files.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from levi.growth.cycle import run_cycle
from levi.lifepack.pack import export_pack, validate_pack
from levi.memory.store import MemoryStore

from ._common import (
    emit,
    finish_step,
    new_step,
    resolve_home,
    utc_now,
    workflow_env,
    workflow_result,
)

NAME = "growth-memory-lifepack"
SUMMARY = (
    "Run one growth cycle (harvest, reflect, consolidate into memory, "
    "journal), then export and validate a life-pack of the LEVI home."
)
STEP_NAMES = ["growth_cycle", "memory_consolidate", "lifepack_export"]


def run(home=None, use_model: bool = False, dry_run: bool = False,
        store: Any = None, **kwargs) -> Dict[str, Any]:
    levi_home = resolve_home(home)
    emit("workflow.start", {"workflow": NAME, "home": str(levi_home),
                            "dry_run": dry_run, "use_model": use_model})
    steps: list = []
    artifacts: Dict[str, Any] = {}

    # -- step 1: growth cycle ----------------------------------------------
    step = new_step("growth_cycle")
    try:
        with workflow_env(levi_home):
            mem_store = store if store is not None else MemoryStore(
                data_dir=levi_home / "memory"
            )
            report = run_cycle(use_model=use_model, dry_run=dry_run, store=mem_store)
        finish_step(step, True, {
            "cycle_id": report.get("cycle_id"),
            "experiences": report.get("experiences"),
            "learnings_proposed": report.get("learnings_proposed"),
            "mode": report.get("mode"),
            "quiet": report.get("quiet"),
        })
        artifacts["cycle_id"] = report.get("cycle_id")
        artifacts["cycle_report"] = report
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- step 2: memory consolidation (what the cycle actually wrote) ------
    step = new_step("memory_consolidate")
    try:
        consolidation = dict(report.get("consolidation") or {})
        accepted = consolidation.get("accepted", 0)
        finish_step(step, True, consolidation)
        artifacts["consolidation"] = consolidation
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    # -- step 3: lifepack export + validate --------------------------------
    step = new_step("lifepack_export")
    try:
        pack = export_pack(home=levi_home)
        validate_pack(pack)
        pack_path = None
        if not dry_run:
            out_dir = levi_home / "lifepacks"
            out_dir.mkdir(parents=True, exist_ok=True)
            pack_path = out_dir / ("workflow-%s.json" % report.get("cycle_id", "no-cycle"))
            pack_path.write_text(
                json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        finish_step(step, True, {
            "pack_path": str(pack_path) if pack_path else None,
            "format": pack.get("format"),
            "version": pack.get("version"),
            "exported_at": pack.get("exported_at"),
            "memory_entries": len((pack.get("sections") or {}).get("memory") or []),
        })
        artifacts["pack_path"] = str(pack_path) if pack_path else None
        artifacts["pack_exported_at"] = pack.get("exported_at")
    except Exception as exc:
        finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
        steps.append(step)
        emit("workflow.done", {"workflow": NAME, "ok": False})
        return workflow_result(NAME, steps, artifacts)
    steps.append(step)

    emit("workflow.done", {"workflow": NAME, "ok": True,
                           "cycle": report.get("cycle_id")})
    return workflow_result(NAME, steps, artifacts)
