"""LEVI Rescue & Remodel — the forge's site-rescue service.

Hierarchy (binding): Alpha & Omega first and last → Levi head of all
beneath them → the rest. This service sits under Levi's head.

Bar Rescue meets Extreme Makeover: Home Edition, directed at businesses
and their websites/apps. Operators walk in on invitation, audit with
evidence, remodel with owner approval, and close with a verified
before/after reveal. Nothing is ever deleted; the stone records every
rescue.

Pipeline: intake → audit → rescue plan → remodel → reveal.
Every consequential step rides the forge rail
(Plan → Preview → Permission → Execute → Verify → Receipt).

Original LEVI-native recreation — never a copy of any existing service.
Not artificial. Synthetic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# -- pipeline stages ---------------------------------------------------------
STAGE_INTAKE = "intake"
STAGE_AUDIT = "audit"
STAGE_PLAN = "plan"
STAGE_REMODEL = "remodel"
STAGE_REVEAL = "reveal"

STAGES = (STAGE_INTAKE, STAGE_AUDIT, STAGE_PLAN, STAGE_REMODEL, STAGE_REVEAL)


def rescue_home(home: "str | Path | None" = None) -> Path:
    """Return the rescue home dir. Never touches the real ~/.levi in tests.

    Explicit ``home`` wins, then ``LEVI_RESCUE_HOME``, then the durable
    ``~/.levi/rescue``.
    """
    if home is not None:
        return Path(home).expanduser()
    env = os.environ.get("LEVI_RESCUE_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".levi" / "rescue"


def ensure_home(home: "str | Path | None" = None) -> Path:
    """Return the rescue home, creating it (owner-only) if missing."""
    root = rescue_home(home)
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    for sub in ("invitations", "audits", "plans", "episodes", "reveals"):
        (root / sub).mkdir(exist_ok=True)
    return root


_rails: Dict[str, Any] = {}


def episode_rail(home: "str | Path | None" = None):
    """One process-scoped rail per rescue home.

    The forge rail keeps pending proposals in memory, so a pipeline run
    (build_plan → approve_plan → run_remodel) shares a single rail per
    home within the process. Receipts still persist to the home's
    ``rail_receipts.jsonl``. Pass an explicit ``rail=`` to any stage to
    override.
    """
    key = str(rescue_home(home).resolve())
    rail = _rails.get(key)
    if rail is None:
        from ..forge.rail import Rail, jsonl_sink

        ensure_home(home)
        rail = Rail(
            receipt_sink=jsonl_sink(rescue_home(home) / "rail_receipts.jsonl"),
            actor="rescue",
        )
        _rails[key] = rail
    return rail


__all__ = [
    "STAGE_INTAKE",
    "STAGE_AUDIT",
    "STAGE_PLAN",
    "STAGE_REMODEL",
    "STAGE_REVEAL",
    "STAGES",
    "ensure_home",
    "episode_rail",
    "rescue_home",
]
