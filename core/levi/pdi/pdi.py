"""Picture Description Instructions: a compact ASCII opcode stream for vector graphics.

Grammar (one opcode per line; ``;`` also separates opcodes on a line;
``#`` starts a comment; blank lines ignored)::

    C                    clear (reset picture, next draw ops start fresh)
    K n                  palette index (0-7)
    P x y                point
    L x1 y1 x2 y2        line
    R x y w h            rect (x, y = lower-left corner)
    E cx cy rx ry        ellipse (center + radii)
    T x y text...        text (rest of the line is literal text)

Coordinates are device-independent: 0..100 in both axes, mapped to the
render target by each renderer. All numeric args must be finite numbers.
Text may be anything except a newline.

Renderers: ``render_svg`` (well-formed SVG), ``render_ascii`` (char-grid
preview). All stdlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

__all__ = [
    "PDIError",
    "Picture",
    "Op",
    "PALETTE",
    "parse",
    "validate",
    "render_svg",
    "render_ascii",
]


class PDIError(Exception):
    """Raised by :func:`parse` on malformed PDI input, with a line number."""


# LEVI's own palette: 8 fixed colors, intentionally NOT the NAPLPS palette.
PALETTE = [
    "#1a1a2e",  # 0 ink black (also the clear background)
    "#e94560",  # 1 signal red
    "#f5a623",  # 2 ember orange
    "#ffd32a",  # 3 beacon yellow
    "#2ed573",  # 4 growth green
    "#1e90ff",  # 5 wire blue
    "#a55eea",  # 6 wyrd violet
    "#f7f1e3",  # 7 paper white
]


@dataclass
class Op:
    """One parsed opcode: ``name`` + args tuple + source line number."""

    name: str
    args: tuple
    line: int


@dataclass
class Picture:
    """A parsed PDI picture: ordered op list + whether C was seen."""

    ops: list[Op] = field(default_factory=list)
    cleared: bool = False


# opcode -> (required arg count, numeric arg count at the front)
_SPECS = {
    "C": (0, 0),
    "K": (1, 1),
    "P": (2, 2),
    "L": (4, 4),
    "R": (4, 4),
    "E": (4, 4),
    "T": (3, 2),  # T x y text...
}


def _num(token: str, lineno: int) -> float:
    try:
        value = float(token)
    except ValueError:
        raise PDIError("line %d: expected a number, got %r" % (lineno, token)) from None
    if not math.isfinite(value):
        raise PDIError("line %d: coordinate must be finite, got %r" % (lineno, token))
    return value


def parse(source: str) -> Picture:
    """Parse a PDI stream into a :class:`Picture`. Raises :class:`PDIError`."""
    pic = Picture()
    lineno = 0
    for raw in source.splitlines():
        lineno += 1
        line = raw.split("#", 1)[0]
        for chunk in line.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split()
            name = parts[0].upper()
            if name not in _SPECS:
                raise PDIError("line %d: unknown opcode %r" % (lineno, parts[0]))
            argc, numc = _SPECS[name]
            rest = parts[1:]
            if name == "T":
                if len(rest) < 2 or len(parts) < 4:
                    raise PDIError("line %d: T needs x, y and text" % lineno)
                x = _num(rest[0], lineno)
                y = _num(rest[1], lineno)
                # Literal text: everything after "T x y " in the raw chunk.
                after = chunk
                for tok in (parts[0], rest[0], rest[1]):
                    pos = after.find(tok)
                    after = after[pos + len(tok) :]
                pic.ops.append(Op(name, (x, y, after.lstrip()), lineno))
                continue
            if len(rest) != argc:
                raise PDIError(
                    "line %d: opcode %s needs %d args, got %d"
                    % (lineno, name, argc, len(rest))
                )
            nums = tuple(_num(t, lineno) for t in rest[:numc])
            if name == "C":
                pic.ops.clear()
                pic.cleared = True
                continue
            if name == "K":
                idx = nums[0]
                if idx != int(idx) or not 0 <= int(idx) <= 7:
                    raise PDIError(
                        "line %d: palette index must be 0-7, got %r" % (lineno, rest[0])
                    )
                pic.ops.append(Op(name, (int(idx),), lineno))
                continue
            pic.ops.append(Op(name, nums, lineno))
    return pic


def validate(source: str) -> list[str]:
    """Non-raising check. Returns ``[]`` when the source is valid."""
    try:
        parse(source)
    except PDIError as exc:
        return [str(exc)]
    return []


def render_svg(picture: Picture, width: int = 320, height: int = 200) -> str:
    """Render a :class:`Picture` to a well-formed SVG string."""
    sx = width / 100.0
    sy = height / 100.0
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">' % (width, height, width, height)
    ]
    if picture.cleared:
        out.append(
            '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>'
            % (width, height, PALETTE[0])
        )
    color = PALETTE[7]
    for op in picture.ops:
        n, a = op.name, op.args
        if n == "K":
            color = PALETTE[a[0]]
        elif n == "P":
            out.append(
                '<circle cx="%.2f" cy="%.2f" r="1.5" fill="%s"/>'
                % (a[0] * sx, a[1] * sy, color)
            )
        elif n == "L":
            out.append(
                '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                'stroke="%s" stroke-width="2"/>'
                % (a[0] * sx, a[1] * sy, a[2] * sx, a[3] * sy, color)
            )
        elif n == "R":
            out.append(
                '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                'fill="none" stroke="%s" stroke-width="2"/>'
                % (a[0] * sx, a[1] * sy, a[2] * sx, a[3] * sy, color)
            )
        elif n == "E":
            out.append(
                '<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                'fill="none" stroke="%s" stroke-width="2"/>'
                % (a[0] * sx, a[1] * sy, a[2] * sx, a[3] * sy, color)
            )
        elif n == "T":
            out.append(
                '<text x="%.2f" y="%.2f" fill="%s" '
                'font-family="monospace" font-size="12">%s</text>'
                % (a[0] * sx, a[1] * sy, color, escape(a[2]))
            )
    out.append("</svg>")
    return "\n".join(out)


def render_ascii(picture: Picture, cols: int = 64, rows: int = 24) -> str:
    """Render a :class:`Picture` as ASCII art on a char grid."""

    def plot(grid, x: float, y: float, ch: str):
        c = int(round(x / 100.0 * (cols - 1)))
        r = int(round(y / 100.0 * (rows - 1)))
        if 0 <= c < cols and 0 <= r < rows:
            grid[r][c] = ch

    grid = [[" "] * cols for _ in range(rows)]
    for op in picture.ops:
        n, a = op.name, op.args
        if n == "P":
            plot(grid, a[0], a[1], "*")
        elif n == "L":
            x0, y0, x1, y1 = a
            dx = x1 - x0
            dy = y1 - y0
            steps = int(max(abs(dx), abs(dy)) * max(cols, rows) / 100.0) or 1
            for i in range(steps + 1):
                t = i / steps
                plot(grid, x0 + dx * t, y0 + dy * t, "#")
        elif n == "R":
            x, y, w, h = a
            for i in range(int(round(w * cols / 100.0)) + 1):
                plot(grid, x + i * 100.0 / cols, y, "-")
                plot(grid, x + i * 100.0 / cols, y + h, "-")
            for i in range(int(round(h * rows / 100.0)) + 1):
                plot(grid, x, y + i * 100.0 / rows, "|")
                plot(grid, x + w, y + i * 100.0 / rows, "|")
            plot(grid, x, y, "+")
            plot(grid, x + w, y, "+")
            plot(grid, x, y + h, "+")
            plot(grid, x + w, y + h, "+")
        elif n == "E":
            cx, cy, rx, ry = a
            for i in range(64):
                t = 2 * math.pi * i / 64
                plot(grid, cx + rx * math.cos(t), cy + ry * math.sin(t), "o")
        elif n == "T":
            x, y, text = a
            for i, ch in enumerate(text):
                if ch == "\n":
                    break
                plot(grid, x + i * 100.0 / cols, y, ch)
        # C is handled at parse time (ops cleared); K is color-only (no ASCII)
    return "\n".join("".join(row).rstrip() for row in grid)
