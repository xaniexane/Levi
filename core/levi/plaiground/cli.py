"""Plaiground CLI — the adult-SI surface, one command tree.

Standalone: ``python -m levi.plaiground <command> ...``

Everything here is gate-checked: with the gate off, only ``gate``
commands run. The gate itself is opened only by the affirmative owner
act (``gate enable --i-affirm-i-am-an-adult``); minors are
hard-locked out.

Top-level hook (for ``cli/main.py`` when ownership is clear)::

    from levi.plaiground.cli import cmd_plaiground, register_plaiground_parser
    register_plaiground_parser(sub)   # in the subparsers block
    "plaiground": cmd_plaiground,     # in the dispatch table
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi plaiground",
        description="Plaiground — the adult-SI surface (gate-checked)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gate", help="Gate enable/disable/status")
    g.add_argument("action", choices=("enable", "disable", "status"))
    g.add_argument("--i-affirm-i-am-an-adult", action="store_true")

    c = sub.add_parser("companion", help="Companion creator")
    c.add_argument("action", choices=("create", "list", "show", "delete"))
    c.add_argument("name", nargs="?")
    c.add_argument("--traits", nargs="*", default=None)
    c.add_argument("--boundaries", nargs="*", default=None)

    s = sub.add_parser("scenario", help="Run a scenario through Echoverse branching")
    s.add_argument("companion")
    s.add_argument("text", nargs="+")
    s.add_argument("--cycles", type=int, default=3)

    st = sub.add_parser("story", help="Adult-fiction writing engine")
    st.add_argument("action", choices=("starter", "character", "arc", "scene", "remix"))
    st.add_argument("--seed", default=None)
    st.add_argument("--name", default=None)
    st.add_argument("--want", default=None)
    st.add_argument("--wound", default=None)
    st.add_argument("--secret", default=None)
    st.add_argument("--beats", type=int, default=5)
    st.add_argument("--setting", default=None)
    st.add_argument("--tension", default="slow-burn")
    st.add_argument("--parts", nargs="*", default=None)

    w = sub.add_parser("wellness", help="Relationship & intimacy wellness")
    w.add_argument("action", choices=("checkin", "deck", "date", "notes", "journal", "custom"))
    w.add_argument("--theme", default=None)
    w.add_argument("--topic", default=None)
    w.add_argument("--count", type=int, default=4)
    w.add_argument("--seed", default=None)
    w.add_argument("--questions", nargs="*", default=None)

    a = sub.add_parser("afterdark", help="Grown-folks entertainment")
    a.add_argument("action", choices=("banter", "starters", "trivia", "game", "round"))
    a.add_argument("--theme", default=None)
    a.add_argument("--kind", default=None)
    a.add_argument("--topic", default=None)
    a.add_argument("--count", type=int, default=4)
    a.add_argument("--seed", default=None)
    a.add_argument("--entries", nargs="*", default=None)

    d = sub.add_parser("depth", help="Companion continuity & rapport")
    d.add_argument("action", choices=("remember", "recall", "rapport", "forget"))
    d.add_argument("companion")
    d.add_argument("--entry", default=None)
    d.add_argument("--kind", default="moment")
    d.add_argument("--limit", type=int, default=10)

    ch = sub.add_parser("chat", help="One tailored chat turn")
    ch.add_argument("companion")
    ch.add_argument("message", nargs="+")
    ch.add_argument("--tone", default="warm")
    return p


def register_plaiground_parser(sub: Any) -> None:
    """Hook for ``cli/main.py``: adds the ``plaiground`` subcommand."""
    parser = sub.add_parser("plaiground", help="Plaiground — the adult-SI surface")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="plaiground subcommand + args")
    parser.set_defaults(_plaiground_dispatch=cmd_plaiground)


def cmd_plaiground(args: Any) -> int:
    """Dispatch for the ``cli/main.py`` hook — passthrough to main()."""
    argv = list(getattr(args, "argv", None) or [])
    return main(argv)


def _print(obj: Any) -> None:
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=2, default=str))


def main(argv: Any = None) -> int:
    args = build_parser().parse_args(argv)
    from levi.plaiground import (
        afterdark,
        chat,
        companions,
        depth,
        gate,
        simulator,
        stories,
        wellness,
    )

    cmd = args.command
    try:
        if cmd == "gate":
            if args.action == "enable":
                if not args.i_affirm_i_am_an_adult:
                    print("REFUSED: pass --i-affirm-i-am-an-adult for the affirmative owner act.")
                    return 2
                path = gate.enable_adult_mode(gate.CONFIRMATION_PHRASE)
                print("Plaiground gate OPEN. Record: %s" % path)
            elif args.action == "disable":
                print("Gate closed." if gate.disable_adult_mode() else "Gate was closed.")
            else:
                _print(gate.status())
            return 0

        if cmd == "companion":
            if args.action == "create":
                if not args.name:
                    print("companion create needs a name"); return 2
                _print(companions.create_companion(args.name, traits=args.traits, boundaries=args.boundaries))
            elif args.action == "list":
                _print(companions.list_companions())
            elif args.action == "show":
                if not args.name:
                    print("companion show needs a name"); return 2
                _print(companions.get_companion(args.name))
            else:
                if not args.name:
                    print("companion delete needs a name"); return 2
                print("Deleted." if companions.delete_companion(args.name) else "No such companion.")
            return 0

        if cmd == "scenario":
            result = simulator.run_scenario(args.companion, " ".join(args.text), cycles=args.cycles)
            print(simulator.format_scenario(result))
            return 0

        if cmd == "story":
            a = args.action
            if a == "starter":
                _print(stories.story_starter(seed=args.seed))
            elif a == "character":
                if not (args.name and args.want and args.wound):
                    print("story character needs --name --want --wound"); return 2
                _print(stories.build_character(args.name, args.want, args.wound, secret=args.secret))
            elif a == "arc":
                _print(stories.weave_arc(beats=args.beats, seed=args.seed))
            elif a == "scene":
                _print(stories.frame_scene(setting=args.setting, tension=args.tension, seed=args.seed))
            else:
                if not args.parts:
                    print("story remix needs --parts ..."); return 2
                _print(stories.remix(args.parts))
            return 0

        if cmd == "wellness":
            a = args.action
            if a == "checkin":
                _print(wellness.checkin(count=args.count, seed=args.seed))
            elif a == "deck":
                if not args.theme:
                    print("wellness deck needs --theme desire|boundaries|appreciation|repair"); return 2
                _print(wellness.prompt_deck(args.theme))
            elif a == "date":
                _print(wellness.plan_date_night(seed=args.seed))
            elif a == "notes":
                if not args.topic:
                    print("wellness notes needs --topic communication|desire|rest|repair"); return 2
                _print(wellness.notes(args.topic))
            elif a == "journal":
                _print(wellness.journal_prompt(seed=args.seed))
            else:
                if not args.questions:
                    print("wellness custom needs --questions ..."); return 2
                _print(wellness.custom_checkin(args.questions))
            return 0

        if cmd == "afterdark":
            a = args.action
            if a == "banter":
                _print(afterdark.banter(seed=args.seed))
            elif a == "starters":
                if not args.theme:
                    print("afterdark starters needs --theme confessions|stories|opinions|deep"); return 2
                _print(afterdark.starters(args.theme, count=args.count))
            elif a == "trivia":
                _print(afterdark.trivia(count=args.count, seed=args.seed))
            elif a == "game":
                if not args.kind:
                    print("afterdark game needs --kind two-truths|would-you-rather|story-round"); return 2
                _print(afterdark.host_game(args.kind, topic=args.topic))
            else:
                if not args.kind or not args.entries:
                    print("afterdark round needs --kind and --entries ..."); return 2
                _print(afterdark.submit_round(args.kind, args.entries))
            return 0

        if cmd == "depth":
            a = args.action
            if a == "remember":
                if not args.entry:
                    print("depth remember needs --entry"); return 2
                _print(depth.remember(args.companion, args.entry, kind=args.kind))
            elif a == "recall":
                _print(depth.recall(args.companion, limit=args.limit))
            elif a == "rapport":
                _print(depth.rapport(args.companion))
            else:
                print("Forgotten." if depth.forget(args.companion) else "Nothing to forget.")
            return 0

        if cmd == "chat":
            session = chat.ChatSession(args.companion, tone=args.tone)
            print(session.say(" ".join(args.message)))
            return 0

        print("unknown command %r" % cmd)
        return 2
    except gate.GateLockedError as exc:
        print("LOCKED: %s" % exc)
        return 1
    except Exception as exc:  # honest errors, never tracebacks
        print("ERROR: %s: %s" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
