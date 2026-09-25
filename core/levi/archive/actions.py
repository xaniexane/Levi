"""Actionable notes \u2014 the Oberon revival for the LEVI Archive.

The Oberon System (ETH Zurich, Wirth & Gutknecht, 1987) unified text
input and command input: commands of the form ``M.P`` "may occur in any
text, and they are activated by pointing at them and clicking the middle
mouse button". The document you read is the command line.

LEVI takes the mechanism, not the mouse chording: a record body may
carry fenced `````levi`` blocks whose lines are ``levi ...`` commands.
``find_actions`` scans a record (Preview); ``run_action`` executes one
action only through an explicit, per-action confirmation gate
(Permission). Two hard boundaries, no exceptions:

1. Only ``levi ...`` commands are actions. Anything else \u2014 raw
   shell, pipes, redirects \u2014 is not an action and never runs. The
   archive can invoke LEVI itself, never an arbitrary shell.
2. Listing is always safe; execution always asks. There is no flag that
   skips the confirmation.

Stdlib only. The default runner executes LEVI's own CLI entry point
in-process; tests inject a fake runner.
"""

from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

#: Fenced blocks tagged ```levi are action sources.
FENCE_RE = re.compile(r"```levi[ \t]*\n(.*?)```", re.DOTALL)

#: Record text fields scanned for action fences.
TEXT_FIELDS = ("summary", "mechanism", "decline", "revival_recipe", "levi_application")

Runner = Callable[[List[str]], int]


@dataclass
class ArchiveAction:
    command: str  # the full command line, e.g. "levi archive stats"
    argv: List[str]  # shlex-split argv (argv[0] == "levi")
    source_field: str  # which record field carried the fence
    line_no: int  # 1-based line within the fence


@dataclass
class ActionScan:
    actions: List[ArchiveAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _parse_fence(
    body: str, source_field: str, warnings: List[str]
) -> List[ArchiveAction]:
    actions: List[ArchiveAction] = []
    for lineno, raw in enumerate(body.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("levi "):
            warnings.append(
                "%s:%d: not a `levi ...` command \u2014 ignored: %r"
                % (source_field, lineno, line[:60])
            )
            continue
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            warnings.append(
                "%s:%d: could not parse \u2014 ignored: %s"
                % (source_field, lineno, exc)
            )
            continue
        actions.append(
            ArchiveAction(
                command=line, argv=argv, source_field=source_field, line_no=lineno
            )
        )
    return actions


def find_actions(record) -> ActionScan:
    """Scan a record's text for `````levi`` action fences.

    Pure and side-effect free: listing actions never executes anything.
    """
    scan = ActionScan()
    for fname in TEXT_FIELDS:
        text = getattr(record, fname, "") or ""
        for fence in FENCE_RE.finditer(text):
            scan.actions.extend(_parse_fence(fence.group(1), fname, scan.warnings))
    return scan


def preview(record) -> str:
    """Human-readable listing of a record's actions (the Preview step)."""
    scan = find_actions(record)
    lines = ["actions in %s:" % record.id]
    if not scan.actions:
        lines.append("  (none)")
    for i, action in enumerate(scan.actions, 1):
        lines.append(
            "  [%d] %s   (%s:%d)"
            % (i, action.command, action.source_field, action.line_no)
        )
    for warning in scan.warnings:
        lines.append("  ! %s" % warning)
    return "\n".join(lines)


def default_runner(argv: List[str]) -> int:
    """Run a ``levi ...`` argv through LEVI's own CLI entry, in-process."""
    from levi.cli.main import main as cli_main

    old_argv = sys.argv
    sys.argv = list(argv)
    try:
        cli_main()
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 1
    finally:
        sys.argv = old_argv
    return 0


def run_action(action: ArchiveAction, runner: Runner | None = None) -> int:
    """Execute one action. The caller owns the confirmation gate."""
    run = runner or default_runner
    return run(action.argv)


def confirm_and_run(
    action: ArchiveAction,
    runner: Runner | None = None,
    ask: Callable[[str], str] | None = None,
) -> Tuple[bool, int]:
    """Ask, then run. Returns ``(ran, exit_code)``.

    ``ask`` defaults to :func:`input`; tests inject a fake. Anything
    other than an explicit ``y``/``yes`` refuses \u2014 fail closed.
    """
    prompt = ask or (lambda p: input(p))
    answer = prompt("run '%s'? [y/N] " % action.command).strip().lower()
    if answer not in ("y", "yes"):
        return False, 0
    return True, run_action(action, runner)
