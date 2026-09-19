"""levi weblayer — the honest Web layer. Usage:

  python -m levi.weblayer demo                      # build a sample canvas
  python -m levi.weblayer validate <canvas.json>    # deny-closed validation
  python -m levi.weblayer export <canvas.json> [--format html|svg] [-o file]
"""

from __future__ import annotations

import argparse
import json
import sys

from .model import Canvas, Hotspot


def _demo() -> Canvas:
    return Canvas(
        width=800, height=600, title="levi weblayer demo", image="demo.png",
        hotspots=[
            Hotspot(id="docs", shape="rect", coords=[40, 40, 200, 80],
                    href="docs/index.html", label="Documentation"),
            Hotspot(id="gallery", shape="ellipse", coords=[560, 200, 120, 80],
                    href="gallery.html", label="Gallery", alt="image gallery"),
            Hotspot(id="play", shape="polygon",
                    coords=[400, 480, 460, 520, 400, 560],
                    href="player.html", label="Play"),
        ])


def _cmd_demo(_args) -> int:
    print(json.dumps(_demo().to_dict(), indent=2))
    return 0


def _load(path: str) -> Canvas:
    with open(path, "r", encoding="utf-8") as fh:
        return Canvas.from_dict(json.load(fh))


def _cmd_validate(args) -> int:
    try:
        c = _load(args.canvas)
    except (OSError, ValueError) as exc:
        print("invalid: %s" % exc, file=sys.stderr)
        return 1
    print("valid: %dx%d, %d hotspots" % (c.width, c.height, len(c.hotspots)))
    return 0


def _cmd_export(args) -> int:
    from .export import to_html, to_svg
    try:
        c = _load(args.canvas)
    except (OSError, ValueError) as exc:
        print("invalid: %s" % exc, file=sys.stderr)
        return 1
    text = to_html(c) if args.format == "html" else to_svg(c)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text, end="")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.weblayer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="print a sample canvas as JSON")
    p = sub.add_parser("validate", help="validate a canvas JSON file")
    p.add_argument("canvas")
    p = sub.add_parser("export", help="export canvas to html or svg")
    p.add_argument("canvas")
    p.add_argument("--format", choices=("html", "svg"), default="html")
    p.add_argument("-o", "--output", default=None)
    args = ap.parse_args(argv)
    return {"demo": _cmd_demo, "validate": _cmd_validate,
            "export": _cmd_export}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
