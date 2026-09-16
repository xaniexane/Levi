"""Entry point: ``python -m levi.bot``.

Subcommands:
- ``chat``    — interactive REPL.
- ``say TEXT`` — one-shot reply, printed to stdout.
- ``persona``  — print the spark voice card (system prompt rendering).
- ``service list`` — list registered services.
- ``service run NAME [--params JSON]`` — execute a service now.
- ``service add --name N --schedule S --type T --description D [--params JSON]``
- ``service remove NAME`` — remove a user-added service (built-ins refuse).
- ``service log [--limit N]`` — show recent service runs.
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_chat(_args: argparse.Namespace) -> int:
    """Run the interactive REPL."""
    from levi.bot.chat import repl

    repl()
    return 0


def _cmd_say(args: argparse.Namespace) -> int:
    """Print a one-shot reply to the given text."""
    from levi.bot.chat import say

    print(say(args.text))
    return 0


def _cmd_persona(_args: argparse.Namespace) -> int:
    """Print the spark voice card / system prompt."""
    from levi.bot.context import build_system_prompt

    print(build_system_prompt())
    return 0


def _cmd_service_list(_args: argparse.Namespace) -> int:
    """Print the registered services."""
    from levi.bot.services import ServiceRegistry

    for svc in ServiceRegistry().list():
        state = "enabled" if svc.enabled else "disabled"
        tag = "builtin" if svc.builtin else "custom"
        print(
            "%s [%s/%s/%s]\n  %s\n  schedule: %s"
            % (svc.name, svc.service_type, tag, state, svc.description, svc.schedule)
        )
    return 0


def _cmd_service_run(args: argparse.Namespace) -> int:
    """Execute a service now and print the narrated report."""
    from levi.bot import automation
    from levi.bot.services import ServiceError

    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except ValueError as exc:
            print("service run: --params must be valid JSON: %s" % exc, file=sys.stderr)
            return 2
        if not isinstance(params, dict):
            print("service run: --params must be a JSON object", file=sys.stderr)
            return 2
    try:
        record = automation.run_service(args.name, params_override=params)
    except ServiceError as exc:
        print("service run: %s" % exc, file=sys.stderr)
        return 1
    print(automation.narrate(record))
    return 0 if record.ok else 1


def _cmd_service_add(args: argparse.Namespace) -> int:
    """Register a new service definition (validated fail-closed)."""
    from levi.bot.services import ServiceDefinition, ServiceError, ServiceRegistry

    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except ValueError as exc:
            print("service add: --params must be valid JSON: %s" % exc, file=sys.stderr)
            return 2
    try:
        svc = ServiceDefinition(
            name=args.name,
            description=args.description,
            service_type=args.type,
            schedule=args.schedule,
            params=params,
        )
        ServiceRegistry().add(svc)
    except ServiceError as exc:
        print("service add: %s" % exc, file=sys.stderr)
        return 1
    print(
        "added service '%s' [%s, schedule %s]"
        % (svc.name, svc.service_type, svc.schedule)
    )
    print("recurrence needs a cron job, e.g.:")
    print(
        "  %s cd %s && python -m levi.bot service run %s"
        % (svc.schedule, _repo_dir(), svc.name)
    )
    return 0


def _repo_dir() -> str:
    """Best-effort repo directory for cron examples."""
    import os

    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return here


def _cmd_service_remove(args: argparse.Namespace) -> int:
    """Remove a user-added service."""
    from levi.bot.services import ServiceError, ServiceRegistry

    try:
        removed = ServiceRegistry().remove(args.name)
    except ServiceError as exc:
        print("service remove: %s" % exc, file=sys.stderr)
        return 1
    if not removed:
        print("service remove: unknown service %r" % (args.name,), file=sys.stderr)
        return 1
    print("removed service '%s'" % args.name)
    return 0


def _cmd_service_log(args: argparse.Namespace) -> int:
    """Print recent service runs."""
    from levi.bot import automation

    runs = automation.read_run_log(limit=args.limit)
    if not runs:
        print("no service runs logged yet")
        return 0
    for run in runs:
        mark = "ok" if run.get("ok") else "FAIL"
        print(
            "%s [%s] %s — %s"
            % (
                run.get("ts", "?")[:19],
                mark,
                run.get("service", "?"),
                run.get("summary", ""),
            )
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``python -m levi.bot``."""
    parser = argparse.ArgumentParser(
        prog="python -m levi.bot",
        description="LEVI conversational bot — spark voice, performed services.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Start an interactive chat session.")
    p_chat.set_defaults(func=_cmd_chat)

    p_say = sub.add_parser("say", help="One-shot reply to the given text.")
    p_say.add_argument("text", help="The message to reply to.")
    p_say.set_defaults(func=_cmd_say)

    p_persona = sub.add_parser(
        "persona", help="Print the spark voice card (system prompt)."
    )
    p_persona.set_defaults(func=_cmd_persona)

    p_service = sub.add_parser(
        "service", help="Performed services: list/run/add/remove/log."
    )
    svc_sub = p_service.add_subparsers(dest="service_command", required=True)

    p_list = svc_sub.add_parser("list", help="List registered services.")
    p_list.set_defaults(func=_cmd_service_list)

    p_run = svc_sub.add_parser("run", help="Execute a service now.")
    p_run.add_argument("name", help="Service name.")
    p_run.add_argument("--params", default=None, help="JSON object of param overrides.")
    p_run.set_defaults(func=_cmd_service_run)

    p_add = svc_sub.add_parser("add", help="Register a new service.")
    p_add.add_argument("--name", required=True, help="Lowercase slug, e.g. my-watch.")
    p_add.add_argument(
        "--schedule",
        required=True,
        help="5-field cron or keyword: hourly/daily/weekly/monthly.",
    )
    p_add.add_argument(
        "--type",
        required=True,
        choices=["briefing", "monitor", "research", "custom"],
        help="Service type.",
    )
    p_add.add_argument("--description", required=True, help="What the service does.")
    p_add.add_argument("--params", default=None, help="JSON object of default params.")
    p_add.set_defaults(func=_cmd_service_add)

    p_remove = svc_sub.add_parser("remove", help="Remove a user-added service.")
    p_remove.add_argument("name", help="Service name.")
    p_remove.set_defaults(func=_cmd_service_remove)

    p_log = svc_sub.add_parser("log", help="Show recent service runs.")
    p_log.add_argument("--limit", type=int, default=20, help="Max records to show.")
    p_log.set_defaults(func=_cmd_service_log)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
