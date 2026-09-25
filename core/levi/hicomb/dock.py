"""Home-agnostic docking: Hicomb <-> builders, either way.

The product-home decision is DECIDED (Chauncey, 2026-09-21): one engine,
three doors — and this module is the Hicomb door. It assumes nothing
about the engine's internals. Instead it offers a dock point: a Hicomb
session can attach the builders engine by reference, and a standalone
builders run can hand its engine to a session later. No import-time
dependency — the builders package is resolved lazily, so a sibling's
in-flight refactor can never break Hicomb's import.

Also hosts the Phase-4 LEVI project-model hook as an honest stub:
it returns None until the daemon wiring is built (a later milestone),
and says so plainly.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field


@dataclass
class DockReport:
    available: bool
    attached: bool
    commands_registered: list[str] = field(default_factory=list)
    note: str = ""


def builders_available() -> bool:
    """Is the sibling builders package importable right now? Lazy, safe."""
    try:
        importlib.import_module("levi.builders")
    except Exception:
        return False
    return True


def dock_builders(session, registry=None, engine=None) -> DockReport:
    """Attach the builders engine to a Hicomb session, home-agnostic.

    - engine=None: construct the sibling's default engine lazily.
    - registry given: registers the ``builders.scaffold`` command so the
      touch command bar can drive prompt -> skeleton -> verify.
    Never raises for a missing/refactoring builders package — it reports.
    """
    try:
        builders = importlib.import_module("levi.builders")
    except Exception as exc:
        return DockReport(
            available=False,
            attached=False,
            note=f"builders package not importable: {exc}",
        )
    if engine is None:
        try:
            engine = builders.ScaffoldEngine()
        except Exception as exc:
            return DockReport(
                available=True,
                attached=False,
                note=f"builders present but engine would not construct: {exc}",
            )
    session.extensions["builders"] = engine
    registered: list[str] = []
    if registry is not None:
        from levi.hicomb.commands import Command

        def _run(sess, args):
            prompt = args.get("prompt", "")
            report = builders.build(prompt) if hasattr(builders, "build") else None
            if report is None:
                return "builders.build not available on this builders revision"
            return f"build {report.outcome}: {report.target_dir}"

        registry.register(
            Command(
                id="builders.scaffold",
                title="Scaffold with Builders",
                touch_label="Build",
                hint="Prompt -> deterministic skeleton (no credit meter)",
                arg_names=("prompt",),
                required_args=("prompt",),
                run=_run,
            )
        )
        registered.append("builders.scaffold")
    return DockReport(
        available=True,
        attached=True,
        commands_registered=registered,
        note="builders engine docked by reference (one engine, three doors)",
    )


def project_model(session):
    """Phase-4 LEVI project-model hook. Honest stub: None until built.

    The unreplicable layer — the file knows the project and the project
    knows the builder — lands in milestone 4/5. Until the daemon wiring
    exists, this returns None and says so; nothing pretends otherwise.
    """
    return None
