"""CLI: python -m levi.games <command>.

Commands:
  charter                     print the Fair Play Charter
  play codebreak              play Codebreak (Mastermind deduction)
  play tictactoe|nim          pass-and-play hotseat match
  cipher [--date YYYY-MM-DD]  play the daily (or any-date) cipher
  cipher-stats                honest stats — celebration only, never punishment
  saves list <game>           list save slots
  saves export <game> <slot> <file>   export a portable save
  saves import <file> [--slot S]      import a portable save
"""

from __future__ import annotations

import argparse
import sys
from datetime import date


def _cmd_charter(_args) -> int:
    from levi.games.charter import charter_text

    print(charter_text())
    return 0


def _cmd_play(args) -> int:
    if args.which == "codebreak":
        from levi.games import deduction

        deduction.play(slot=args.slot)
    elif args.which in ("tictactoe", "nim"):
        from levi.games import hotseat

        cls = hotseat.TABLES[args.which]
        hotseat.play_hotseat(cls(), slot=args.slot)
    else:
        print("unknown game %r (try codebreak, tictactoe, nim)" % args.which)
        return 2
    return 0


def _cmd_cipher(args) -> int:
    from levi.games import daily_puzzle

    day = date.fromisoformat(args.date) if args.date else None
    daily_puzzle.play(day)
    return 0


def _cmd_cipher_stats(_args) -> int:
    from levi.games import daily_puzzle

    s = daily_puzzle.stats()
    print("Daily Cipher — honest stats")
    print("  puzzles played : %d" % s["played"])
    print("  solved         : %d" % s["solved"])
    print(
        "  current streak : %d  (celebration only — missing a day breaks nothing)"
        % s["current_streak"]
    )
    print("  free hints used: %d" % s["total_hints"])
    return 0


def _cmd_saves(args) -> int:
    from levi.games.saves import SaveStore, SaveError

    store = SaveStore()
    try:
        if args.action == "list":
            slots = store.list_slots(args.game)
            print("slots for %s: %s" % (args.game, ", ".join(slots) or "(none)"))
        elif args.action == "export":
            path = store.export(args.game, args.slot, args.file)
            print("exported to %s — yours to keep" % path)
        elif args.action == "import":
            game_id, slot = store.import_save(args.file, args.slot)
            print("imported as %s slot %r" % (game_id, slot))
        else:
            print("unknown saves action %r" % args.action)
            return 2
    except SaveError as exc:
        print("save error: %s" % exc)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.games", description="Fair-play local games"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("charter", help="print the Fair Play Charter")

    play_p = sub.add_parser("play", help="play a game")
    play_p.add_argument("which", choices=["codebreak", "tictactoe", "nim"])
    play_p.add_argument("--slot", default=None, help="save slot (defaults per game)")

    cipher_p = sub.add_parser("cipher", help="play the daily cipher")
    cipher_p.add_argument(
        "--date", default=None, help="any date YYYY-MM-DD — catch up freely"
    )
    sub.add_parser("cipher-stats", help="honest cipher stats")

    saves_p = sub.add_parser("saves", help="player-owned saves")
    saves_p.add_argument("action", choices=["list", "export", "import"])
    saves_p.add_argument("game", nargs="?", default=None)
    saves_p.add_argument("slot", nargs="?", default=None)
    saves_p.add_argument("file", nargs="?", default=None)

    args = parser.parse_args(argv)
    if args.command == "charter":
        return _cmd_charter(args)
    if args.command == "play":
        return _cmd_play(args)
    if args.command == "cipher":
        return _cmd_cipher(args)
    if args.command == "cipher-stats":
        return _cmd_cipher_stats(args)
    if args.command == "saves":
        return _cmd_saves(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
