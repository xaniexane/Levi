"""Typed ordered action stream: the build's internal representation.

Competitor builders emit typed, ordered actions (Bolt's <boltAction>
file/shell/start/supabase, v0's CodeProject blocks, Replit's
directory_structure JSON) rather than a bag of files. Ordering is explicit:
dependencies and scaffolding before verification, migrations before boot.

An ActionPlan is deterministic in the BuildPlan that produced it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from levi.builders.planner import BuildPlan

# Action types. Keep the vocabulary small and mechanical.
WRITE_FILE = "write_file"  # create/overwrite one file
RUN = "run"  # run a local command (verification only, never installs)
MIGRATE = "migrate"  # schema/data bootstrap step (a file, applied in order)


@dataclass
class Action:
    type: str
    path: str = ""  # target file for write_file / migrate
    command: List[str] = field(default_factory=list)  # argv for run
    detail: str = ""


@dataclass
class ActionPlan:
    plan: BuildPlan
    actions: List[Action]

    def write_actions(self) -> List[Action]:
        return [a for a in self.actions if a.type in (WRITE_FILE, MIGRATE)]


def _order_key(path: str) -> tuple:
    """Deterministic generation order: packages, then entry-adjacent
    modules, then the rest alphabetically, then tests last.

    Mirrors Bolt's "package.json first" instinct: foundations stream
    before the things that depend on them.
    """
    if path.endswith("__init__.py"):
        return (0, path)
    if path.startswith("migrations/"):
        return (1, path)
    if path.startswith("tests/"):
        return (3, path)
    if path in ("README.md", "theme.yaml", ".provenance.json", ".env.example"):
        return (4, path)
    return (2, path)


def plan_actions(build_plan: BuildPlan, files: Dict[str, str]) -> ActionPlan:
    """Turn a plan + generated file set into an ordered action stream."""
    actions: List[Action] = []
    for path in sorted(files, key=_order_key):
        atype = WRITE_FILE
        if path.startswith("migrations/"):
            atype = MIGRATE
        actions.append(
            Action(
                type=atype,
                path=path,
                detail="emit %s" % path,
            )
        )
    # Verification runs after every file exists — order matters.
    actions.append(
        Action(
            type=RUN,
            command=["compileall"],
            detail="byte-compile every generated python file",
        )
    )
    return ActionPlan(plan=build_plan, actions=actions)


def apply_actions(action_plan: ActionPlan, target_dir: str, files: Dict[str, str]) -> List[str]:
    """Apply write/migrate actions to disk. Returns paths written, in order."""
    written: List[str] = []
    for action in action_plan.write_actions():
        content = files.get(action.path)
        if content is None:
            continue
        full = os.path.join(target_dir, action.path)
        os.makedirs(os.path.dirname(full) or target_dir, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(action.path)
    return written
