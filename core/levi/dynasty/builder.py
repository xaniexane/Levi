# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""The Dynasty Builder agent spec — the trainee-class agent that serves.

Honest boundary, stated plainly: the Builder is registered in the
dynasty's OWN registry (:mod:`levi.dynasty.registry`), which mirrors
the nursery workload laws — seeded facts first, judgment earned,
verification before acceptance. It is NOT enrolled in the nursery
router: the router's law admits only graduated trainees, and the
Builder never graduates. It serves. Registration is a record of
standing, not a graduation certificate.

Tool scopes are hard rails, not suggestions: ``file_write`` may touch
only ``core/levi/dynasty/shell/``; ``test_run`` may run only the
dynasty test files; ``snapshot_capture`` may capture only through the
day-0 snapshot helper; ``commission_agent`` may commission wave-kin
through :meth:`levi.dynasty.dna.DynastyAgent.commission_kin` — id and
profile validation, wave-registry enrollment with generation and
commissioned_by, and the sealed birth receipt — and nothing else.
Everything else is a ScopeViolation.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

#: The one directory the Builder is ever allowed to write into.
WRITE_SCOPE = "core/levi/dynasty/shell/"


class ScopeViolation(ValueError):
    """A tool was used outside its declared scope."""


BUILDER_SPEC: Dict[str, object] = {
    "name": "dynasty-builder",
    "agent_class": "trainee-class",
    "serves": "never graduates — it serves",
    "tools": [
        {
            "name": "file_write",
            "scope": "core/levi/dynasty/shell/ ONLY — the CLI prototype skeleton",
        },
        {
            "name": "test_run",
            "scope": "may run pytest on tests/test_dynasty.py and tests/test_dynasty_ip.py only",
        },
        {
            "name": "snapshot_capture",
            "scope": "may capture via levi.dynasty.snapshot.capture_dynasty_day0 only",
        },
        {
            "name": "commission_agent",
            "scope": (
                "may commission wave-kin via "
                "levi.dynasty.dna.DynastyAgent.commission_kin only: "
                "new-id + proficiency-profile validation, wave-registry "
                "enrollment (generation, commissioned_by, attributes, "
                "kind from the open taxonomy), "
                "sealed wave.commission birth receipt. No file writes, "
                "no network, no money."
            ),
        },
    ],
    "rails": [
        {"name": "no_network", "value": True},
        {"name": "no_money", "value": True},
    ],
}

#: New wave-kin ids: lowercase, 3..32 chars, letters/digits/underscore.
_COMMISSION_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")

_KNOWN_TOOLS = {t["name"] for t in BUILDER_SPEC["tools"]}


def _within_write_scope(target: str) -> bool:
    """True iff the normalized target stays inside WRITE_SCOPE."""
    norm = os.path.normpath(target)
    return norm == WRITE_SCOPE.rstrip("/") or norm.startswith(WRITE_SCOPE)


def check_tool_scope(tool: str, target: str) -> None:
    """Validate a Builder tool call against its declared scope.

    Raises :class:`ScopeViolation` when the tool is unknown, when a
    ``file_write`` target escapes ``core/levi/dynasty/shell/`` (including
    any ``..`` traversal attempt), when a ``commission_agent`` target is
    not a well-formed new kin id, or when the target is empty.
    """
    if tool not in _KNOWN_TOOLS:
        raise ScopeViolation(f"unknown tool: {tool!r}")
    if tool == "commission_agent":
        if not target or not target.strip():
            raise ScopeViolation("commission_agent requires a new kin id")
        if not _COMMISSION_ID_RE.match(target.strip()):
            raise ScopeViolation(
                f"commission_agent rejects malformed kin id: {target!r}"
            )
        return
    if tool != "file_write":
        return  # test_run and snapshot_capture carry their scope in the declaration
    if not target or not target.strip():
        raise ScopeViolation("file_write requires a non-empty target")
    parts = re.split(r"[\\/]", target)
    if ".." in parts:
        raise ScopeViolation(f"path traversal rejected: {target!r}")
    if os.path.isabs(target):
        raise ScopeViolation(f"absolute paths are outside scope: {target!r}")
    if not _within_write_scope(target):
        raise ScopeViolation(f"file_write target {target!r} escapes {WRITE_SCOPE!r}")


def list_tools() -> List[str]:
    """Return the declared tool names."""
    return sorted(_KNOWN_TOOLS)


def get_rail(name: str) -> Optional[bool]:
    """Return the value of a named rail, or None when undeclared."""
    for rail in BUILDER_SPEC["rails"]:
        if rail["name"] == name:
            return rail["value"]
    return None
