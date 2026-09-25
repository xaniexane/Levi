"""``python -m levi.mind`` — the one-command ceremony for the runner.

    python -m levi.mind start            # wake the mind (guard verifies first)
    python -m levi.mind stop             # put the mind down
    python -m levi.mind status [--json]  # running / stopped / stale
    python -m levi.mind guard  [--json]  # show the offline-mandatory verdict

Plain speech by default; ``--json`` for scripts. ``--home`` overrides the
mind home (``~/.levi/mind/``, or ``LEVI_MIND_HOME``). Nothing here leaves
the machine: there is no network call in this package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.mind import config as mind_config
from levi.mind import daemon as mind_daemon
from levi.mind import guard


def _emit(result: dict, as_json: bool, code: int) -> int:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        detail = result.get("detail", "")
        state = result.get("state", "")
        verdict = (result.get("verdict") or {}).get("verdict", "")
        bits = [p for p in (state, verdict, detail) if p]
        print("  ".join(bits) if bits else json.dumps(result, default=str))
        reasons = (result.get("verdict") or {}).get("reasons") or []
        if verdict == "refused":
            for reason in reasons:
                print(f"  - {reason}")
    return code


def _cmd_status(home: Path, as_json: bool) -> int:
    result = mind_daemon.status(home)
    return _emit(result, as_json, mind_daemon.EXIT_OK)


def _cmd_start(home: Path, as_json: bool) -> int:
    code, result = mind_daemon.start(home)
    return _emit(result, as_json, code)


def _cmd_stop(home: Path, as_json: bool) -> int:
    code, result = mind_daemon.stop(home)
    return _emit(result, as_json, code)


def _cmd_guard(home: Path, as_json: bool) -> int:
    try:
        cfg = mind_config.ensure(home)
    except ValueError as exc:
        report = guard.GuardReport(guard.Verdict.UNCERTAIN, [str(exc)])
    else:
        report = guard.check(cfg)
    code = mind_daemon.EXIT_OK if report.allowed else mind_daemon.EXIT_REFUSED
    return _emit({"verdict": report.as_dict()}, as_json, code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m levi.mind")
    parser.add_argument("--home", default=None, help="mind home directory")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "command",
        choices=["start", "stop", "status", "guard"],
        help="start | stop | status | guard",
    )
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser() if args.home else mind_config.mind_home()

    commands = {
        "start": _cmd_start,
        "stop": _cmd_stop,
        "status": _cmd_status,
        "guard": _cmd_guard,
    }
    try:
        return commands[args.command](home, args.json)
    except KeyboardInterrupt:
        print("interrupted")
        return mind_daemon.EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
