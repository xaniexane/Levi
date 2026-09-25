"""CLI: python -m levi.pdi <command> [options]

Render PDI opcode streams to ASCII art or SVG, or validate a stream.
"""

from __future__ import annotations

import argparse
import sys

from .pdi import parse, validate, render_svg, render_ascii, PDIError


def _read_source(path):
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    return sys.stdin.read()


def _cmd_render(a) -> int:
    source = _read_source(a.file)
    try:
        pic = parse(source)
    except PDIError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if a.svg:
        print(render_svg(pic, width=a.width, height=a.height))
    else:
        print(render_ascii(pic, cols=a.cols, rows=a.rows))
    return 0


def _cmd_validate(a) -> int:
    errors = validate(_read_source(a.file))
    if errors:
        for e in errors:
            print("error: %s" % e, file=sys.stderr)
        return 1
    print("valid")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.pdi",
        description="PDI: ASCII opcode streams for vector graphics",
    )
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("render", help="render a PDI stream (default: ASCII art)")
    r.add_argument("file", nargs="?", default=None, help="PDI file (stdin if omitted)")
    r.add_argument("--svg", action="store_true", help="emit SVG instead of ASCII")
    r.add_argument("--ascii", action="store_true", help="emit ASCII art (default)")
    r.add_argument("--cols", type=int, default=64, help="ASCII grid columns")
    r.add_argument("--rows", type=int, default=24, help="ASCII grid rows")
    r.add_argument("--width", type=int, default=320, help="SVG width")
    r.add_argument("--height", type=int, default=200, help="SVG height")

    v = sub.add_parser("validate", help="check a PDI stream for errors")
    v.add_argument("file", nargs="?", default=None, help="PDI file (stdin if omitted)")

    a = p.parse_args(argv)
    handlers = {
        "render": _cmd_render,
        "validate": _cmd_validate,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
