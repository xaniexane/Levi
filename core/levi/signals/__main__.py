"""``python -m levi.signals`` — inspect and exercise the signal plane.

Commands run in the foreground and exit; nothing is installed or forked.

Usage:
    python -m levi.signals status
    python -m levi.signals test-fire [--mode focus|plan|review|play] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from levi.signals.focus import Mode, get_mode
from levi.signals.grades import route
from levi.signals.hours import DEFAULT_ACTIVE_HOURS
from levi.signals.instincts import levi_home
from levi.signals.wiring import (
    default_registry,
    deliver,
    gather_evidence,
)


def _print_status(home: str | None) -> int:
    base = Path(home).expanduser() if home else levi_home()
    reg = default_registry(home=base)
    state_path = base / "signals" / "cooldowns.json"
    last_fired: dict = {}
    try:
        last_fired = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(last_fired, dict):
            last_fired = {}
    except (OSError, json.JSONDecodeError):
        pass
    print("signal plane status")
    print("  home:          %s" % base)
    print("  mode:          %s" % get_mode(base).value)
    print(
        "  active hours:  %02d:%02d–%02d:%02d local"
        % (
            DEFAULT_ACTIVE_HOURS.start[0],
            DEFAULT_ACTIVE_HOURS.start[1],
            DEFAULT_ACTIVE_HOURS.end[0],
            DEFAULT_ACTIVE_HOURS.end[1],
        )
    )
    print("  instincts:     %d wired" % len(reg.list()))
    for inst in reg.list():
        last = last_fired.get(inst.id, "never")
        print("    - %s" % inst.id)
        print(
            "        fires_on: %s | cooldown: %ds | max_grade: %s"
            % (inst.fires_on, inst.cooldown, inst.max_grade.name)
        )
        print("        does: %s" % inst.does)
        print("        last fired: %s" % last)
    return 0


def _print_test_fire(home: str | None, mode: str | None, as_json: bool) -> int:
    base = Path(home).expanduser() if home else levi_home()
    now = datetime.now().astimezone()
    evidence = gather_evidence(base, now)
    reg = default_registry(home=base)
    signals = reg.evaluate(evidence, now)
    active_mode = Mode(mode) if mode else get_mode(base)
    delivered = deliver(signals, home=base, mode=active_mode, now=now)
    if as_json:
        payload = {
            "home": str(base),
            "mode": active_mode.value,
            "evidence": evidence,
            "signals": [
                {
                    "grade": s.grade.name,
                    "tag": s.tag,
                    "title": s.title,
                    "body": s.body,
                    "actions": list(s.actions),
                    "requires_ack": s.requires_ack,
                    "due_now": s.due_now,
                    "source": s.source,
                }
                for s in signals
            ],
            "delivered": [s.title for s in delivered],
        }
        print(json.dumps(payload, indent=2))
        return 0
    print(
        "test-fire @ %s  mode=%s"
        % (now.isoformat(timespec="seconds"), active_mode.value)
    )
    interesting = {k: v for k, v in evidence.items() if v}
    print("evidence: %s" % (interesting or "none — instincts stay silent"))
    print("signals fired: %d" % len(signals))
    for signal in signals:
        delivery = route(signal)
        print(
            "  [%s] %s %s (surface=%s, delivered=%s)"
            % (
                signal.grade.name,
                signal.tag,
                signal.title,
                delivery.surface,
                delivery.delivered,
            )
        )
    if delivered:
        print("--- delivered ---")
        for signal in delivered:
            text = route(signal).render()
            if text:
                print(text)
                print("---")
    else:
        print("delivered: none (held by cooldown, focus mute, or hours gate)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m levi.signals",
        description="Inspect and exercise the LEVI signal plane.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="LEVI home dir (default: $LEVI_HOME or ~/.levi)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show wired instincts, mode, hours, cooldowns.")
    tf = sub.add_parser("test-fire", help="Evaluate instincts against live evidence.")
    tf.add_argument(
        "--mode",
        default=None,
        choices=[m.value for m in Mode],
        help="Override the persisted mode for this run.",
    )
    tf.add_argument("--json", action="store_true", help="Emit JSON.")

    args = parser.parse_args(argv)
    if args.command == "test-fire":
        return _print_test_fire(args.home, args.mode, args.json)
    # Default: status.
    return _print_status(args.home)


if __name__ == "__main__":
    sys.exit(main())
