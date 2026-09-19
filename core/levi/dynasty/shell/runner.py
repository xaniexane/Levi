# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Guarded command runner — subprocess with a hard deny-list.

``CommandRunner.run(argv, timeout=30)`` executes a command via
:func:`subprocess.run` and returns ``{stdout, stderr, returncode}``.

Hard rails, stated plainly:
- ``argv`` MUST be a list — anything else is refused. ``shell=True``
  is never used, anywhere, for any reason.
- :data:`DENY_PATTERNS` is a deny-list of destructive commands
  (``rm -rf /``, ``rm -rf ~``, ``mkfs``, the fork bomb, ``dd`` to a
  device, ``shutdown``, ``reboot``). A match raises
  :class:`RefusedCommand` BEFORE anything executes.
"""

from __future__ import annotations

import re
import subprocess
from typing import Dict, List, Sequence


class RefusedCommand(ValueError):
    """A command was refused by the deny-list or the argv contract."""


#: Destructive commands this runner will never execute. Matched
#: against the command line joined with spaces, case-insensitively.
DENY_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\brm\b.*\s-rf?\s+/(?:\s|$)", re.IGNORECASE),  # rm -rf /
    re.compile(r"\brm\b.*\s-rf?\s+~(?:\s|$|/)", re.IGNORECASE),  # rm -rf ~
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:.*&\s*\}\s*;?\s*:", re.IGNORECASE),  # fork bomb
    re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
]


def _refuse_if_destructive(argv: List[str]) -> None:
    command_line = " ".join(argv)
    for pattern in DENY_PATTERNS:
        if pattern.search(command_line):
            raise RefusedCommand(f"refused destructive command: {command_line!r}")


class CommandRunner:
    """Runs subprocesses under the argv contract and the deny-list."""

    def run(self, argv: Sequence[str], timeout: int = 30) -> Dict[str, object]:
        """Run ``argv`` and return ``{stdout, stderr, returncode}``.

        Raises :class:`RefusedCommand` when ``argv`` is not a list of
        strings or matches a deny-list pattern. A timeout surfaces as
        ``{stdout, stderr, returncode: -1}`` with a ``"timed out"``
        note in stderr — it does not crash the caller.
        """
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(a, str) for a in argv)
        ):
            raise RefusedCommand("argv must be a non-empty list of strings")
        _refuse_if_destructive(argv)
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": exc.stdout or "",
                "stderr": ((exc.stderr or "") + "\n[timed out]").strip(),
                "returncode": -1,
            }
        except OSError as exc:
            return {"stdout": "", "stderr": str(exc), "returncode": -1}
        return {
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "returncode": proc.returncode,
        }
