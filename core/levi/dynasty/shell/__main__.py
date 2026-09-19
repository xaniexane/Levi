# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shell CLI — JSON over argparse. ``python -m levi.dynasty.shell``.

Commands:
    sessions create <name> [--shell-command CMD] | sessions list | sessions kill <name>
    run -- <argv...>                       (-- separates CLI flags from argv)
    hook register <name> -- <argv...> | hook run <name> | hook list | hook remove <name>

State persists in ``<LEVI_HOME>/dynasty/shell/state.json`` (falls back
to ``~/.levi``). Every command prints JSON to stdout; errors print a
JSON ``{"error": ...}`` and exit non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _default_state_file() -> Path:
    return _home() / "dynasty" / "shell" / "state.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="levi.dynasty.shell", description="Shell prototype CLI"
    )
    sub = parser.add_subparsers(dest="top", required=True)

    p_sess = sub.add_parser("sessions")
    sess_sub = p_sess.add_subparsers(dest="sessions_action", required=True)
    p_create = sess_sub.add_parser("create")
    p_create.add_argument("name")
    p_create.add_argument("--shell-command", dest="shell_command", default=None)
    sess_sub.add_parser("list")
    p_kill = sess_sub.add_parser("kill")
    p_kill.add_argument("name")

    p_run = sub.add_parser("run")
    p_run.add_argument("argv", nargs=argparse.REMAINDER)

    p_hook = sub.add_parser("hook")
    hook_sub = p_hook.add_subparsers(dest="hook_action", required=True)
    p_reg = hook_sub.add_parser("register")
    p_reg.add_argument("name")
    p_reg.add_argument("argv", nargs=argparse.REMAINDER)
    p_hrun = hook_sub.add_parser("run")
    p_hrun.add_argument("name")
    hook_sub.add_parser("list")
    p_rm = hook_sub.add_parser("remove")
    p_rm.add_argument("name")
    return parser


def _clean(argv_list) -> list:
    return [a for a in argv_list if a != "--"]


def main(argv=None) -> int:
    from levi.dynasty.shell.hooks import AutomationHooks
    from levi.dynasty.shell.runner import CommandRunner
    from levi.dynasty.shell.sessions import SessionManager

    args = _build_parser().parse_args(argv)
    sessions = SessionManager(state_file=_default_state_file())
    try:
        if args.top == "sessions":
            if args.sessions_action == "create":
                result = sessions.create(args.name, command=args.shell_command)
            elif args.sessions_action == "list":
                result = sessions.list_sessions()
            elif args.sessions_action == "kill":
                result = sessions.kill(args.name)
        elif args.top == "run":
            result = CommandRunner().run(_clean(args.argv))
        elif args.top == "hook":
            hooks = AutomationHooks()
            if args.hook_action == "register":
                result = hooks.register(args.name, _clean(args.argv))
            elif args.hook_action == "run":
                result = hooks.run(args.name)
            elif args.hook_action == "list":
                result = hooks.list_hooks()
            elif args.hook_action == "remove":
                hooks.remove(args.name)
                result = {"removed": args.name}
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except ValueError as exc:  # SessionError / HookError / RefusedCommand
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
