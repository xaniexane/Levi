# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Automation hooks — named runnable recipes over the command runner.

A hook is ``{name, argv, schedule_note}``: a named command an agent or
script can fire. :class:`AutomationHooks` registers, runs (delegating
to :class:`~levi.dynasty.shell.runner.CommandRunner`), lists, and
removes hooks. Unknown or duplicate names raise :class:`HookError`.
All registered hooks live in memory; the deny-list in
:mod:`~levi.dynasty.shell.runner` still applies at run time.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Union

from levi.dynasty.shell.runner import CommandRunner


class HookError(ValueError):
    """A hook operation was refused (duplicate or unknown name)."""


class AutomationHooks:
    """Named automation hooks over the guarded command runner."""

    def __init__(self, runner: Union[CommandRunner, None] = None) -> None:
        self._runner = runner if runner is not None else CommandRunner()
        self._hooks: Dict[str, Dict[str, object]] = {}

    def register(
        self, name: str, argv: Sequence[str], schedule_note: str = ""
    ) -> Dict[str, object]:
        """Register a hook. Raises :class:`HookError` on duplicate names
        and on a non-list ``argv`` (the runner's contract)."""
        if not name or not name.strip():
            raise HookError("hook name must be non-empty")
        if name in self._hooks:
            raise HookError(f"duplicate hook: {name!r}")
        argv_list = list(argv)
        if not argv_list or not all(isinstance(a, str) for a in argv_list):
            raise HookError("hook argv must be a non-empty list of strings")
        hook = {"name": name, "argv": argv_list, "schedule_note": schedule_note}
        self._hooks[name] = hook
        return dict(hook)

    def run(self, name: str) -> Dict[str, object]:
        """Run a registered hook. Raises :class:`HookError` when unknown;
        a refused command raises :class:`RefusedCommand` from the runner."""
        hook = self._hooks.get(name)
        if hook is None:
            raise HookError(f"unknown hook: {name!r}")
        result = self._runner.run(list(hook["argv"]))
        return {"hook": name, **result}

    def list_hooks(self) -> List[Dict[str, object]]:
        """Return copies of all registered hooks."""
        return [dict(h) for h in self._hooks.values()]

    def remove(self, name: str) -> None:
        """Remove a hook. Raises :class:`HookError` when unknown."""
        if name not in self._hooks:
            raise HookError(f"unknown hook: {name!r}")
        del self._hooks[name]
