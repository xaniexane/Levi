"""CLI: python -m levi.desk [render|tiles|add|remove|move|enable|disable|prefs]

Your own status desk: tiles you choose, in the order you choose, with
your own preferences. Nothing ranked, nothing recommended, nothing sold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .layout import DeskLayout
from .registry import TileError, TileRegistry, register_builtin_tiles
from .render import render_desk


def _registry() -> TileRegistry:
    reg = TileRegistry()
    register_builtin_tiles(reg)
    return reg


def _cmd_render(a) -> int:
    sys.stdout.write(render_desk(_registry()))
    return 0


def _cmd_tiles(a) -> int:
    for d in _registry().describe():
        print("%-10s %s — %s" % (d["name"], d["title"], d["description"]))
    return 0


def _cmd_layout(a) -> int:
    for i, e in enumerate(DeskLayout().entries()):
        print("%d. %s  enabled=%s  prefs=%s"
              % (i, e["tile"], e["enabled"], json.dumps(e["prefs"])))
    return 0


def _cmd_add(a) -> int:
    prefs = json.loads(a.prefs) if a.prefs else None
    DeskLayout().add(a.name, prefs=prefs, position=a.position)
    print("added %s to the desk" % a.name)
    return 0


def _cmd_remove(a) -> int:
    DeskLayout().remove(a.name)
    print("removed %s from the desk" % a.name)
    return 0


def _cmd_move(a) -> int:
    DeskLayout().move(a.name, a.position)
    print("moved %s to position %d" % (a.name, a.position))
    return 0


def _cmd_enable(a) -> int:
    DeskLayout().set_enabled(a.name, True)
    print("enabled %s" % a.name)
    return 0


def _cmd_disable(a) -> int:
    DeskLayout().set_enabled(a.name, False)
    print("disabled %s" % a.name)
    return 0


def _cmd_prefs(a) -> int:
    DeskLayout().set_prefs(a.name, json.loads(a.prefs))
    print("prefs set for %s" % a.name)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m levi.desk")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("render", help="print the desk").set_defaults(f=_cmd_render)
    sub.add_parser("tiles", help="list registered tiles").set_defaults(f=_cmd_tiles)
    sub.add_parser("layout", help="show the current layout").set_defaults(f=_cmd_layout)
    p = sub.add_parser("add", help="add a tile to the desk")
    p.add_argument("name"); p.add_argument("--prefs", default=None)
    p.add_argument("--position", type=int, default=None)
    p.set_defaults(f=_cmd_add)
    p = sub.add_parser("remove", help="remove a tile from the desk")
    p.add_argument("name"); p.set_defaults(f=_cmd_remove)
    p = sub.add_parser("move", help="move a tile to a position")
    p.add_argument("name"); p.add_argument("position", type=int)
    p.set_defaults(f=_cmd_move)
    p = sub.add_parser("enable", help="enable a tile")
    p.add_argument("name"); p.set_defaults(f=_cmd_enable)
    p = sub.add_parser("disable", help="disable a tile")
    p.add_argument("name"); p.set_defaults(f=_cmd_disable)
    p = sub.add_parser("prefs", help="replace a tile's prefs (JSON)")
    p.add_argument("name"); p.add_argument("prefs")
    p.set_defaults(f=_cmd_prefs)
    a = ap.parse_args(argv)
    if not a.cmd:
        a = ap.parse_args(["render"])
    try:
        return a.f(a)
    except TileError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except ValueError as exc:
        print("error: bad JSON: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
