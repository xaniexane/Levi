"""CLI: python -m levi.doors <command> [options]

The door launcher: write drop files, check/spend daily turns, and play
the bundled doors.
"""

from __future__ import annotations

import argparse
import sys

from . import doors


def _cmd_drop(a) -> int:
    path = doors.write_drop(
        a.path,
        node=a.node,
        handle=a.handle,
        time_left_s=a.time_left,
        level=a.level,
        door=a.door,
        extra={"argv": a.extra} if a.extra else None,
    )
    print(path)
    return 0


def _cmd_turn(a) -> int:
    ledger = doors.TurnLedger()
    if a.spend:
        ok = ledger.spend_turn(a.player, a.door, a.per_day)
        left = ledger.turns_left(a.player, a.door, a.per_day)
        print("spent=%s turns_left=%d" % ("true" if ok else "false", left))
        return 0 if ok else 1
    print(ledger.turns_left(a.player, a.door, a.per_day))
    return 0


def _cmd_play(a) -> int:
    if a.door != "oracle":
        print("unknown door: %s" % a.door, file=sys.stderr)
        return 1
    res = doors.play_oracle(a.handle, guess=a.guess, per_day=a.per_day)
    outcome = res["outcome"]
    if outcome == "prompt":
        print("number oracle: guess 1..100 (turns left: %d)" % res["turns_left"])
    elif outcome == "no-turns":
        print("no turns left today — come back tomorrow", file=sys.stderr)
        return 1
    elif outcome == "correct":
        print("correct! (turns left: %d)" % res["turns_left"])
    else:
        print("the number is %s (turns left: %d)" % (outcome, res["turns_left"]))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.doors",
        description="LEVI doors: BBS-style door plugins via JSON drop files",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("drop", help="write a JSON drop file carrying player context")
    d.add_argument("--path", required=True)
    d.add_argument("--node", required=True)
    d.add_argument("--handle", required=True)
    d.add_argument("--time-left", type=int, required=True)
    d.add_argument("--level", type=int, required=True)
    d.add_argument("--door", required=True)
    d.add_argument("--extra", nargs="*", default=[], help="door-specific extras")

    t = sub.add_parser("turn", help="check or spend today's turns")
    t.add_argument("--player", required=True)
    t.add_argument("--door", required=True)
    t.add_argument("--per-day", type=int, default=3)
    t.add_argument("--spend", action="store_true", help="spend one turn")

    pl = sub.add_parser("play", help="play a door")
    pl.add_argument("--handle", required=True)
    pl.add_argument("--door", default="oracle", choices=["oracle"])
    pl.add_argument("--guess", type=int, default=None)
    pl.add_argument("--per-day", type=int, default=3)

    a = p.parse_args(argv)
    handlers = {
        "drop": _cmd_drop,
        "turn": _cmd_turn,
        "play": _cmd_play,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
