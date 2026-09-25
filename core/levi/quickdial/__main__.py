"""CLI: python -m levi.quickdial <command> [options]

Opera's Speed Dial, LEVI-native: pin named workflow slots, dial them back
instantly, bind single-key chords. ``dial`` prints the exact command line;
only ``--run`` executes it (via os.execvp, no shell, no pipes, no chaining).
"""

from __future__ import annotations

import argparse
import os
import sys

from . import (
    dial as _dial,
    find,
    find_by_chord,
    load,
    pin,
    render,
    seed,
    unpin,
)


def _cmd_pin(a) -> int:
    try:
        slot = pin(
            a.name,
            a.cmdline,  # argv list from the ``--`` remainder, verbatim
            description=a.description or "",
            chord=a.chord or "",
            replace=a.replace,
        )
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    extra = "  chord=%r" % slot.chord if slot.chord else ""
    print("pinned %r -> %s%s" % (slot.name, render(slot), extra))
    return 0


def _cmd_unpin(a) -> int:
    if unpin(a.name):
        print("unpinned %r" % a.name)
        return 0
    print("no such slot: %r" % a.name, file=sys.stderr)
    return 1


def _cmd_list(a) -> int:
    slots = load()
    if not slots:
        print("no dials pinned yet — try: python -m levi.quickdial seed")
        return 0
    for i, s in enumerate(slots, 1):
        chord = " [%s]" % s.chord if s.chord else ""
        desc = " — %s" % s.description if s.description else ""
        uses = " (dialed %d×)" % s.uses if s.uses else ""
        print("%2d. %s%s%s: %s%s" % (i, s.name, chord, uses, render(s), desc))
    return 0


def _run(argv) -> int:
    # One argv, one process, owner's eyes only. No shell, no pipes.
    os.execvp(argv[0], argv)
    return 0  # unreachable


def _cmd_dial(a) -> int:
    try:
        slot = find_by_chord(a.chord) if a.chord else find(a.slot)
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    argv = _dial(slot)
    print(render(slot))
    if a.run:
        return _run(argv)
    return 0


def _cmd_seed(a) -> int:
    added = seed()
    if not added:
        print("starter dials already present")
        return 0
    for s in added:
        print("pinned %r -> %s" % (s.name, render(s)))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.quickdial",
        description="Speed-Dial-style workflow slots for LEVI (Opera's killed power-user layer, reborn)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pn = sub.add_parser("pin", help="pin a command line to a named slot")
    pn.add_argument("name", help="slot name (lowercase, digits, -, _)")
    pn.add_argument(
        "cmdline", nargs=argparse.REMAINDER, help="command line to pin, after --"
    )
    pn.add_argument("--description", default="")
    pn.add_argument(
        "--chord", default="", help="single-key chord binding (Opera gesture nod)"
    )
    pn.add_argument("--replace", action="store_true")

    up = sub.add_parser("unpin", help="remove a slot")
    up.add_argument("name")

    sub.add_parser("list", help="list pinned dials")

    d = sub.add_parser("dial", help="recall a slot (print; --run to execute)")
    d.add_argument("slot", nargs="?", default="", help="slot name or 1-based number")
    d.add_argument("--chord", default="", help="dial by chord key")
    d.add_argument("--run", action="store_true", help="execute via execvp (no shell)")

    sub.add_parser("seed", help="pin the starter set of LEVI workflows")

    a = p.parse_args(argv)
    handlers = {
        "pin": _cmd_pin,
        "unpin": _cmd_unpin,
        "list": _cmd_list,
        "dial": _cmd_dial,
        "seed": _cmd_seed,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
