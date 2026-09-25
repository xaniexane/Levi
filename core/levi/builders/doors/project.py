"""Graduation path: one project, three doors, no rebuild.

A project scaffolded through any door opens identically through the
others. The engine is deterministic — the same prompt through any door
yields byte-identical output — so graduation is a change of *surface*,
never a rebuild. :class:`DoorReport.continue_via` enforces that
invariant loudly: if two doors ever diverge on the same prompt, it
raises instead of drifting silently.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from levi.builders.pipeline import BuildReport
from levi.builders.verify import BuildOutcome

_PROVENANCE_FILE = ".provenance.json"
_BUILDER_PROVENANCE = "builder"


class NotABuilderProject(ValueError):
    """Raised when a directory has no builder provenance to open."""


class GraduationMismatch(AssertionError):
    """Raised when two doors diverge on the same prompt.

    The one-engine contract says this can never happen. If it does, the
    doors are no longer thin — fix the door, never the project.
    """


def _read_tree(root: str) -> Dict[str, bytes]:
    tree: Dict[str, bytes] = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                tree[os.path.relpath(full, root)] = fh.read()
    return tree


def _read_provenance(target_dir: str) -> Dict:
    prov_file = os.path.join(target_dir, _PROVENANCE_FILE)
    if not os.path.isfile(prov_file):
        raise NotABuilderProject(
            "no %s in %r — not a builders project" % (_PROVENANCE_FILE, target_dir)
        )
    with open(prov_file, "r", encoding="utf-8") as fh:
        prov = json.load(fh)
    if prov.get("provenance") != _BUILDER_PROVENANCE:
        raise NotABuilderProject(
            "provenance %r is not a builders project" % (prov.get("provenance"),)
        )
    return prov


@dataclass
class DoorReport:
    """What a door returns: the engine's report, tagged with its door.

    The door adds surface, never logic — every field below comes straight
    from the shared engine's :class:`BuildReport`.
    """

    door: str
    prompt: str
    build_report: BuildReport

    @property
    def outcome(self) -> BuildOutcome:
        return self.build_report.outcome

    @property
    def ok(self) -> bool:
        return self.build_report.ok

    @property
    def target_dir(self) -> str:
        return self.build_report.target_dir

    @property
    def files(self) -> List[str]:
        return self.build_report.files

    @property
    def attempts(self) -> int:
        return self.build_report.attempts

    @property
    def repairs(self) -> List[str]:
        return self.build_report.repairs

    @property
    def provenance(self) -> Dict:
        """The project's provenance manifest, read back from disk."""
        return _read_provenance(self.target_dir)

    def open_project(self) -> "Project":
        """Open the built project as a door-agnostic handle."""
        return open_project(self.target_dir)

    def continue_via(
        self,
        other_build: Callable[..., "DoorReport"],
        workdir: Optional[str] = None,
        **kwargs,
    ) -> "DoorReport":
        """Graduate: run the same prompt through another door.

        Returns the other door's report. Raises :class:`GraduationMismatch`
        if the outputs differ by even one byte — the doors must stay thin.
        """
        other = other_build(self.prompt, workdir=workdir, **kwargs)
        mine, theirs = _read_tree(self.target_dir), _read_tree(other.target_dir)
        if mine != theirs:
            only_mine = sorted(set(mine) - set(theirs))
            only_theirs = sorted(set(theirs) - set(mine))
            changed = sorted(p for p in set(mine) & set(theirs) if mine[p] != theirs[p])
            raise GraduationMismatch(
                "door %r diverged from door %r on the same prompt "
                "(only in %s: %s; only in %s: %s; changed: %s)"
                % (
                    self.door,
                    other.door,
                    self.door,
                    only_mine,
                    other.door,
                    only_theirs,
                    changed,
                )
            )
        if self.provenance != other.provenance:
            raise GraduationMismatch(
                "door %r provenance diverged from door %r" % (self.door, other.door)
            )
        return other


@dataclass
class Project:
    """A builders project on disk, openable through any door.

    Carries no door affinity: it was verified once by the engine, and any
    door can present it, extend it, or hand it to another surface.
    """

    path: str
    provenance: Dict = field(default_factory=dict)

    @property
    def app(self) -> Optional[str]:
        return self.provenance.get("app")

    @property
    def entities(self) -> List[str]:
        return list(self.provenance.get("entities", []))

    @property
    def prompt_sha256(self) -> Optional[str]:
        return self.provenance.get("prompt_sha256")


def open_project(path: str) -> Project:
    """Open a builders project directory through any door.

    Raises :class:`NotABuilderProject` for directories the engine did not
    produce — a door never claims a foreign project.
    """
    if not os.path.isdir(path):
        raise NotABuilderProject("not a directory: %r" % (path,))
    return Project(path=os.path.abspath(path), provenance=_read_provenance(path))
