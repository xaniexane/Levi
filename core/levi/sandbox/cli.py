"""``levi sandbox`` CLI: run commands in an isolated Linux environment.

Original LEVI work. stdlib-only.

- ``levi sandbox info`` — show every backend, its availability, and the honest
  isolation contract (guarantees + limitations). Read-only; always safe.
- ``levi sandbox run [--net] [--backend auto|bubblewrap|unshare|subprocess]
  [--repo PATH] -- <cmd...>`` — run a command in the best available backend.
  The backend name and isolation level are printed BEFORE execution, and the
  degraded subprocess backend requires ``--i-understand`` after a LOUD
  warning. The child inherits stdio; ``levi`` exits with the child's code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .backends import describe_backends, isolation_report, select_backend
from .runner import run_command

_DEGRADED_BANNER = """\
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!  DEGRADED SANDBOX — NO ISOLATION                                         !!
!!  This run uses plain `subprocess`: the command below will run with YOUR  !!
!!  user, YOUR filesystem, YOUR home directory and YOUR network. Nothing   !!
!!  is contained. Do not run untrusted code.                                !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\
"""


def register_sandbox(sub) -> None:
    try:
        sb = sub.add_parser(
            "sandbox",
            help="run experimental work in an isolated Linux environment",
        )
    except argparse.ArgumentError:
        # Name collision: an older region already owns `sandbox` (the legacy
        # syntax+smoke command, `levi sandbox --path`). Attach our subcommands
        # to that existing parser instead of replacing it, so the legacy
        # invocation keeps working. `_name_parser_map` is argparse-internal;
        # if it ever disappears we surface the original conflict loudly.
        try:
            sb = sub._name_parser_map["sandbox"]  # noqa: SLF001
        except (AttributeError, KeyError):
            raise
    cmds = sb.add_subparsers(dest="sandbox_cmd")

    cmds.add_parser("info", help="show sandbox backends and their isolation contracts")

    run_p = cmds.add_parser("run", help="run a command in the best available sandbox")
    run_p.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "bubblewrap", "unshare", "subprocess"],
        help="force a backend (default: auto = strongest available)",
    )
    run_p.add_argument(
        "--net",
        action="store_true",
        help="allow network access inside the sandbox (bubblewrap only; "
        "other backends always share your network — see `levi sandbox info`)",
    )
    run_p.add_argument(
        "--repo",
        default=None,
        help="working directory inside the sandbox (default: this repo checkout)",
    )
    run_p.add_argument(
        "--i-understand",
        action="store_true",
        help="acknowledge the LOUD warning and allow the degraded "
        "no-isolation subprocess backend",
    )
    run_p.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="command to run, after `--` (e.g. `levi sandbox run -- pytest -x`)",
    )


def cmd_sandbox_info(args) -> None:
    for spec in describe_backends():
        status = "available" if spec.available else "NOT FOUND on PATH"
        print(f"--- {spec.name}  [{status}]")
        print(isolation_report(spec))
        print()


def cmd_sandbox_run(args) -> None:
    user_cmd = list(args.cmd or [])
    # argparse.REMAINDER keeps the leading `--`; drop it.
    if user_cmd[:1] == ["--"]:
        user_cmd = user_cmd[1:]
    if not user_cmd:
        print("usage: levi sandbox run -- <command> [args...]", file=sys.stderr)
        sys.exit(2)

    try:
        spec = select_backend(None if args.backend == "auto" else args.backend)
    except ValueError as e:
        print(f"sandbox: {e}", file=sys.stderr)
        sys.exit(2)

    # Honesty first: say what isolation we actually have BEFORE running.
    print(f"sandbox backend : {spec.name}")
    print(f"isolation level : {spec.isolation_level}")
    if args.net and spec.name == "bubblewrap":
        print("network         : ENABLED inside sandbox (--net)")
    elif spec.name == "bubblewrap":
        print("network         : disabled (empty network namespace)")
    else:
        print("network         : SHARED with host (this backend cannot isolate it)")
    print(f"command         : {' '.join(user_cmd)}")
    print()

    if spec.name == "subprocess" and not args.i_understand:
        print(_DEGRADED_BANNER, file=sys.stderr)
        print(file=sys.stderr)
        print(
            "Refusing to run: pass --i-understand to acknowledge no isolation.",
            file=sys.stderr,
        )
        sys.exit(2)

    repo = Path(args.repo).resolve() if args.repo else None
    sys.stdout.flush()  # keep the pre-run report ahead of the child's output
    result = run_command(
        user_cmd,
        backend=args.backend if args.backend != "auto" else None,
        net=args.net,
        repo=repo,
        allow_degraded=args.i_understand,
    )
    for note in result.notes:
        print(f"sandbox note: {note}")
    sys.exit(result.returncode)


def cmd_sandbox(args) -> None:
    action = getattr(args, "sandbox_cmd", None)
    if action == "info":
        cmd_sandbox_info(args)
    elif action == "run":
        cmd_sandbox_run(args)
    else:
        # No subcommand: this is the legacy `levi sandbox --path` invocation
        # owned by another region. Delegate to it (deferred import: levi.cli
        # is fully loaded by dispatch time, so this is not circular).
        from levi.cli.main import cmd_sandbox as _legacy_cmd_sandbox

        _legacy_cmd_sandbox(args)
