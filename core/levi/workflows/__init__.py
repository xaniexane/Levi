"""Flagship cross-module workflows (Megazord axis 5).

Adapters over the real module APIs — perpetual hunts, the archive, the
galaxy registry, the growth loop, memory, and life-packs — chained into
end-to-end, offline, bounded runs.

Stable contract::

    list_workflows() -> list[dict]      # name, summary, steps per workflow
    run_workflow(name, home=None, **kwargs) -> dict
        # {workflow, ok, started_at, finished_at, steps, artifacts}

Unknown workflow name -> ValueError.  Failures are honest: ok=False with a
reason, never fabricated results.
"""

from __future__ import annotations

from . import (archive_showcase, forge_ci_export, growth_memory_lifepack,
                hunt_archive_publish)
from .registry import list_workflows, register, run_workflow

register(hunt_archive_publish.NAME, hunt_archive_publish.SUMMARY,
         hunt_archive_publish.STEP_NAMES, hunt_archive_publish.run)
register(growth_memory_lifepack.NAME, growth_memory_lifepack.SUMMARY,
         growth_memory_lifepack.STEP_NAMES, growth_memory_lifepack.run)
register(archive_showcase.NAME, archive_showcase.SUMMARY,
         archive_showcase.STEP_NAMES, archive_showcase.run)
register(forge_ci_export.NAME, forge_ci_export.SUMMARY,
         forge_ci_export.STEP_NAMES, forge_ci_export.run)

__all__ = ["list_workflows", "run_workflow", "register"]
