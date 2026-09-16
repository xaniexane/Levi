"""CLI: python -m levi.games <command>.

Commands:
  charter                     print the Fair Play Charter
  play codebreak              play Codebreak (Mastermind deduction)
  play tictactoe|nim          pass-and-play hotseat match
  cipher [--date YYYY-MM-DD]  play the daily (or any-date) cipher
  cipher-stats                honest stats — celebration only, never punishment
  bagatelle [--angle DEG] [--force N] [--seed N] [--layout S] [--prove]
                            launch a bagatelle ball; --prove prints empirical odds
  mancala [--variant NAME] [--move N] [--generate] [--validate] [--seed N]
                            play a mancala variant move, or generate+validate one
  story [--adventure NAME]   play a parser interactive fiction (Z-machine revival)
  odds [--crate NAME] [--prove]
                            the anti-loot-box: free pulls, published odds, --prove audits
  season <new|add|log|status|close|reopen> ...
                            the un-expiring battle pass — progress never rots
  relay <new|move|show|verify|export|import> ...
                            async turn relay: the BBS-door ritual as a protocol
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


def _cmd_bagatelle(args) -> int:
    from levi.games import bagatelle

    board = (
        bagatelle.BagatelleBoard.from_layout_string(args.layout)
        if args.layout
        else bagatelle.classic_board()
    )
    if args.prove:
        bagatelle.empirical_distribution(
            board,
            trials=args.trials,
            seed=args.seed or 7,
            angle_deg=args.angle,
            force=args.force,
        )
        return 0
    try:
        res = bagatelle.simulate(
            board,
            args.angle,
            args.force,
            seed=args.seed,
        )
    except bagatelle.StepBudgetExceeded as exc:
        print("the ball never settled: %s" % exc)
        return 1
    print(bagatelle.render_ascii(board, res.path_sample))
    if res.pocket_hit is not None:
        print(
            "pocket %d after %d steps  (angle=%g force=%g)"
            % (res.pocket_hit.score, res.steps, args.angle, args.force)
        )
    else:
        print("the ball came to rest on the pins after %d steps" % res.steps)
    print("layout: %s" % board.layout_string())
    return 0


def _cmd_mancala(args) -> int:
    import json

    from levi.games import mancala

    if args.generate or args.validate:
        rules = mancala.generate_variant(args.seed or 0)
        print("generated:", json.dumps(rules.to_dict(), sort_keys=True))
        try:
            plies = mancala.validate_variant(rules)
        except Exception as exc:
            print("INVALID: %s" % exc)
            return 1
        print("valid: greedy self-play terminated in %d plies" % plies)
        return 0
    rules = mancala.VARIANTS.get(args.variant, mancala.VARIANTS["kalah"])
    state = mancala.new_state(rules)
    if args.move is not None:
        try:
            state = mancala.play(state, args.move)
        except mancala.IllegalMove as exc:
            print("illegal move: %s" % exc)
            return 1
    print(
        "variant: %s %s" % (args.variant, json.dumps(rules.to_dict(), sort_keys=True))
    )
    print(mancala.render(state))
    print("legal moves: %s" % mancala.legal_moves(state))
    return 0


def _cmd_story(args) -> int:
    from levi.games import if_engine

    adv = if_engine.ADVENTURES.get(args.adventure)
    if adv is None:
        print(
            "unknown adventure %r (try: %s)"
            % (args.adventure, ", ".join(if_engine.ADVENTURES))
        )
        return 2
    if_engine.play(adv, slot=args.slot or "story")
    return 0


def _cmd_odds(args) -> int:
    from levi.games import odds

    if args.crate not in odds.CRATES:
        print("unknown crate %r (try: %s)" % (args.crate, ", ".join(odds.CRATES)))
        return 2
    if args.prove:
        print(odds.prove(args.crate, n=args.trials, seed=args.seed or 7))
        return 0
    odds.play(args.crate, slot=args.slot or "crate")
    return 0


def _cmd_season(args) -> int:
    from levi.games import season

    return season.cmd(args)


def _cmd_relay(args) -> int:
    from levi.games import relay

    return relay.cmd(args)


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

    bag_p = sub.add_parser("bagatelle", help="launch a bagatelle ball")
    bag_p.add_argument(
        "--angle", type=float, default=90.0, help="launch angle in degrees"
    )
    bag_p.add_argument("--force", type=float, default=260.0, help="launch force")
    bag_p.add_argument("--seed", type=int, default=None, help="deterministic run")
    bag_p.add_argument(
        "--layout",
        default=None,
        help="board layout string (omit for the classic board)",
    )
    bag_p.add_argument(
        "--prove",
        action="store_true",
        help="print the empirical pocket odds instead of playing",
    )
    bag_p.add_argument("--trials", type=int, default=20000, help="trials for --prove")

    man_p = sub.add_parser("mancala", help="play or generate a mancala variant")
    man_p.add_argument(
        "--variant", default="kalah", choices=["kalah", "oware", "omweso_lite"]
    )
    man_p.add_argument(
        "--move", type=int, default=None, help="apply this pit move and show the board"
    )
    man_p.add_argument(
        "--generate", action="store_true", help="generate a random ruleset"
    )
    man_p.add_argument(
        "--validate",
        action="store_true",
        help="generate and self-play-validate a ruleset",
    )
    man_p.add_argument(
        "--seed", type=int, default=None, help="seed for --generate/--validate"
    )

    saves_p = sub.add_parser("saves", help="player-owned saves")
    saves_p.add_argument("action", choices=["list", "export", "import"])
    saves_p.add_argument("game", nargs="?", default=None)
    saves_p.add_argument("slot", nargs="?", default=None)
    saves_p.add_argument("file", nargs="?", default=None)

    story_p = sub.add_parser(
        "story", help="parser interactive fiction (Z-machine revival)"
    )
    story_p.add_argument("--adventure", default="sunken-archive")
    story_p.add_argument("--slot", default=None, help="save slot")

    odds_p = sub.add_parser(
        "odds", help="the anti-loot-box: free pulls, published odds"
    )
    odds_p.add_argument("--crate", default="starfall")
    odds_p.add_argument("--slot", default=None, help="save slot")
    odds_p.add_argument("--prove", action="store_true", help="empirical odds audit")
    odds_p.add_argument("--trials", type=int, default=20000, help="trials for --prove")
    odds_p.add_argument("--seed", type=int, default=None, help="seed for --prove")

    season_p = sub.add_parser("season", help="the un-expiring battle pass")
    season_p.add_argument(
        "action", choices=["new", "add", "log", "status", "close", "reopen"]
    )
    season_p.add_argument("name", nargs="?", default=None, help="season name (new)")
    season_p.add_argument("--cid", default=None, help="challenge id (add/log)")
    season_p.add_argument("--desc", default="", help="challenge description (add)")
    season_p.add_argument(
        "--target", type=int, default=1, help="challenge target (add)"
    )
    season_p.add_argument(
        "--xp", type=int, default=50, help="challenge xp reward (add)"
    )
    season_p.add_argument("--amount", type=int, default=1, help="progress to log (log)")
    season_p.add_argument("--slot", default="season", help="save slot")

    relay_p = sub.add_parser(
        "relay", help="async turn relay (BBS-door ritual as protocol)"
    )
    relay_p.add_argument(
        "action", choices=["new", "move", "show", "verify", "export", "import"]
    )
    relay_p.add_argument("players", nargs="*", default=[], help="player names (new)")
    relay_p.add_argument("--player", default=None, help="moving player (move)")
    relay_p.add_argument(
        "--move", default="{}", help="move payload, JSON or text (move)"
    )
    relay_p.add_argument("--file", default=None, help="relay file (export/import)")
    relay_p.add_argument("--slot", default="relay", help="save slot")

    args = parser.parse_args(argv)
    if args.command == "charter":
        return _cmd_charter(args)
    if args.command == "play":
        return _cmd_play(args)
    if args.command == "cipher":
        return _cmd_cipher(args)
    if args.command == "cipher-stats":
        return _cmd_cipher_stats(args)
    if args.command == "bagatelle":
        return _cmd_bagatelle(args)
    if args.command == "mancala":
        return _cmd_mancala(args)
    if args.command == "saves":
        return _cmd_saves(args)
    if args.command == "story":
        return _cmd_story(args)
    if args.command == "odds":
        return _cmd_odds(args)
    if args.command == "season":
        return _cmd_season(args)
    if args.command == "relay":
        return _cmd_relay(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
