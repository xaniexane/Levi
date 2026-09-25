"""``python -m levi.daemon`` — foreground entrypoint for the unified supervisor.

Commands run in the foreground and exit; nothing is installed as an OS
daemon, a systemd unit, a launchd plist, or a cron job. The user owns their
machine.

Usage:
    python -m levi.daemon pulse          # run every health check once
    python -m levi.daemon list           # show the service catalog
    python -m levi.daemon status [name]  # health of one service (or all)
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.daemon.supervisor import Supervisor


def _print_pulse(sup: Supervisor) -> int:
    report = sup.supervise_once()
    print(f"pulse @ {report['ran_at']}  home={report['home']}")
    print(f"services: {report['up']}/{report['total']} up")
    for name, st in report["services"].items():
        mark = "UP  " if st["ok"] else "DOWN"
        print(f"  [{mark}] {name:18s} {st['detail']}")
    return 0 if report["down"] == 0 else 1


def _print_list(sup: Supervisor) -> int:
    for entry in sup.list_services():
        print(f"{entry['name']}")
        print(f"  module:     {entry['module']}")
        print(f"  summary:    {entry['summary']}")
        print(f"  start_hint: {entry['start_hint']}")
    return 0


def _print_status(sup: Supervisor, name: str | None, as_json: bool) -> int:
    if name:
        payload = sup.service_status(name)
        ok = payload["ok"]
    else:
        payload = sup.all_status()
        ok = all(s["ok"] for s in payload.values())
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        items = [payload] if name else payload.values()
        for st in items:  # type: ignore[union-attr]
            mark = "UP  " if st["ok"] else "DOWN"
            print(f"[{mark}] {st['name']}: {st['detail']}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m levi.daemon",
        description="Unified foreground supervisor for every LEVI service.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="LEVI home dir (default: $LEVI_HOME or ~/.levi)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("pulse", help="Run every health check once and report.")
    sub.add_parser("list", help="Show the service catalog.")
    st = sub.add_parser("status", help="Health of one service (or all).")
    st.add_argument(
        "name", nargs="?", default=None, help="Service name from the catalog."
    )
    st.add_argument("--json", action="store_true", help="Emit JSON.")

    args = parser.parse_args(argv)
    sup = Supervisor(home=args.home)

    if args.command == "list":
        return _print_list(sup)
    if args.command == "status":
        return _print_status(sup, args.name, args.json)
    # Default: pulse.
    return _print_pulse(sup)


if __name__ == "__main__":
    sys.exit(main())
