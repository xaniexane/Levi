"""Picture Description Instructions with macros and DRCS, NAPLPS shaped.

Studied from: dead-networks-20260916/report.md [NAPLPS]

Functional description: drawings are streams of ASCII PDI opcodes where
each opcode byte is followed by coordinate data packed as printable 6-bit
strings — every axis value is split into 6-bit groups offset by 0x20 so
the whole stream survives 7-bit text channels, and a leading count byte
says how many groups each axis carries (2, 3, or 4, so resolution is
variable). On top of the drawing opcodes the module adds two NAPLPS
signature mechanisms: macros (define a named sequence of opcodes once,
invoke it by name anywhere) and DRCS — downloadable character sets, where
glyph bitmaps are stored under code points and later placed as text. The
``Canvas`` records macro definitions, DRCS fonts, and the live drawing;
``encode`` emits the full PDI stream, ``decode`` replays it, expanding
macros at decode time and resolving DRCS text against the stored fonts.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: the opcode set covers point/line/rectangle/polygon/
circle/text plus macro define/invoke and DRCS load/use; variable group
counts of 2–4 per axis cap coordinates at 24 bits; macro bodies may not
nest definitions (invocation may nest); DRCS glyphs are bit-rows, and
this module does not rasterize them to pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/pdi-graphics"

# PDI opcodes (ASCII)
OP_POINT = "P"
OP_LINE = "D"  # draw
OP_RECT = "R"
OP_POLY = "Y"  # polygon
OP_CIRCLE = "O"
OP_TEXT = "T"
OP_MACRO_DEF = "M"
OP_MACRO_RUN = "X"
OP_DRCS_LOAD = "F"  # font load
OP_DRCS_TEXT = "G"  # DRCS text placement

_DRAW_OPS = {OP_POINT, OP_LINE, OP_RECT, OP_POLY, OP_CIRCLE, OP_TEXT}
_ALL_OPS = _DRAW_OPS | {OP_MACRO_DEF, OP_MACRO_RUN, OP_DRCS_LOAD, OP_DRCS_TEXT}

_OFFSET = 0x20
_GROUP_COUNTS = (2, 3, 4)


class PDIError(ValueError):
    """Raised for bad PDI streams, macros, or DRCS data."""


def encode_value(value: int, groups: int = 3) -> str:
    """Pack an unsigned value as ``groups`` printable 6-bit characters."""
    if groups not in _GROUP_COUNTS:
        raise PDIError(f"group count must be one of {_GROUP_COUNTS}")
    if not (0 <= value < (1 << (6 * groups))):
        raise PDIError(f"value {value} does not fit in {groups} groups")
    out = []
    for i in range(groups - 1, -1, -1):
        out.append(chr(_OFFSET + ((value >> (6 * i)) & 0x3F)))
    return "".join(out)


def decode_value(text: str) -> int:
    value = 0
    for ch in text:
        group = ord(ch) - _OFFSET
        if not (0 <= group < 64):
            raise PDIError(f"group character {ch!r} out of range")
        value = (value << 6) | group
    return value


def _count_byte(groups: int) -> str:
    return chr(ord("0") + groups)


def encode_xy(x: int, y: int, groups: int = 3) -> str:
    return _count_byte(groups) + encode_value(x, groups) + encode_value(y, groups)


def _read_xy(stream: str, pos: int) -> Tuple[Tuple[int, int], int, int]:
    """Read one XY pair; returns (point, groups, new_pos)."""
    if pos >= len(stream):
        raise PDIError("truncated XY data")
    groups = ord(stream[pos]) - ord("0")
    pos += 1
    if groups not in _GROUP_COUNTS:
        raise PDIError(f"bad group count {groups}")
    need = 2 * groups
    if pos + need > len(stream):
        raise PDIError("truncated XY data")
    x = decode_value(stream[pos : pos + groups])
    y = decode_value(stream[pos + groups : pos + need])
    return (x, y), groups, pos + need


@dataclass
class Macro:
    name: str
    body: str  # raw PDI body (draw opcodes only)


@dataclass
class DRCSFont:
    name: str
    glyphs: Dict[int, List[str]] = field(default_factory=dict)  # codepoint -> bit-rows


@dataclass
class Canvas:
    """A PDI canvas: macros, DRCS fonts, and the drawing instruction list."""

    groups: int = 3
    macros: Dict[str, Macro] = field(default_factory=dict)
    fonts: Dict[str, DRCSFont] = field(default_factory=dict)
    stream: List[str] = field(default_factory=list)

    # -- drawing ------------------------------------------------------
    def _coords(self, points: List[Tuple[int, int]]) -> str:
        return "".join(encode_xy(x, y, self.groups) for x, y in points)

    def point(self, x: int, y: int) -> "Canvas":
        self.stream.append(OP_POINT + self._coords([(x, y)]))
        return self

    def line(self, x1: int, y1: int, x2: int, y2: int) -> "Canvas":
        self.stream.append(OP_LINE + self._coords([(x1, y1), (x2, y2)]))
        return self

    def rect(self, x1: int, y1: int, x2: int, y2: int) -> "Canvas":
        self.stream.append(OP_RECT + self._coords([(x1, y1), (x2, y2)]))
        return self

    def polygon(self, points: List[Tuple[int, int]]) -> "Canvas":
        if len(points) < 3:
            raise PDIError("polygon needs at least 3 points")
        n = encode_value(len(points), 2)
        self.stream.append(OP_POLY + n + self._coords(points))
        return self

    def circle(self, cx: int, cy: int, r: int) -> "Canvas":
        self.stream.append(OP_CIRCLE + self._coords([(cx, cy), (r, 0)]))
        return self

    def text(self, x: int, y: int, content: str) -> "Canvas":
        if not content.isascii():
            raise PDIError("text must be ASCII")
        n = encode_value(len(content), 2)
        self.stream.append(OP_TEXT + self._coords([(x, y)]) + n + content)
        return self

    # -- macros --------------------------------------------------------
    def define_macro(self, name: str, body: str) -> "Canvas":
        if not name.isascii() or not name.isalnum() or len(name) > 8:
            raise PDIError("macro name must be 1-8 ASCII alphanumerics")
        for ch in body:
            if ch in (OP_MACRO_DEF, OP_MACRO_RUN):
                raise PDIError("macro bodies may not define or run macros")
        self.macros[name] = Macro(name, body)
        n = encode_value(len(name), 2)
        m = encode_value(len(body), 2)
        self.stream.append(OP_MACRO_DEF + n + name + m + body)
        return self

    def run_macro(self, name: str) -> "Canvas":
        if name not in self.macros:
            raise PDIError(f"undefined macro {name!r}")
        n = encode_value(len(name), 2)
        self.stream.append(OP_MACRO_RUN + n + name)
        return self

    # -- DRCS ----------------------------------------------------------
    def load_font(self, name: str, glyphs: Dict[int, List[str]]) -> "Canvas":
        for code, rows in glyphs.items():
            if not rows or any(set(r) - {"0", "1"} for r in rows):
                raise PDIError(f"glyph {code} rows must be bit strings")
        self.fonts[name] = DRCSFont(name, dict(glyphs))
        payload = []
        for code, rows in glyphs.items():
            payload.append(encode_value(code, 2))
            payload.append(encode_value(len(rows), 2))
            for row in rows:
                payload.append(encode_value(int(row, 2), 2))
                payload.append(encode_value(len(row), 2))
        n = encode_value(len(name), 2)
        total = encode_value(sum(len(p) for p in payload), 3)
        self.stream.append(OP_DRCS_LOAD + n + name + total + "".join(payload))
        return self

    def drcs_text(self, font: str, x: int, y: int, codepoints: List[int]) -> "Canvas":
        if font not in self.fonts:
            raise PDIError(f"unknown DRCS font {font!r}")
        n = encode_value(len(font), 2)
        cps = "".join(encode_value(c, 2) for c in codepoints)
        m = encode_value(len(codepoints), 2)
        self.stream.append(OP_DRCS_TEXT + n + font + self._coords([(x, y)]) + m + cps)
        return self

    # -- encode / decode ----------------------------------------------
    def encode(self) -> str:
        return "".join(self.stream)

    @classmethod
    def decode(cls, data: str) -> "Canvas":
        canvas = cls()
        pos = 0
        while pos < len(data):
            op = data[pos]
            pos += 1
            if op not in _ALL_OPS:
                raise PDIError(f"unknown opcode {op!r}")
            if op in (OP_POINT, OP_LINE, OP_RECT):
                need = 1 if op == OP_POINT else 2
                pts = []
                seen_groups = None
                for _ in range(need):
                    pt, groups, pos = _read_xy(data, pos)
                    pts.append(pt)
                    seen_groups = groups
                canvas.stream.append(
                    op + "".join(encode_xy(x, y, seen_groups) for x, y in pts)
                )
            elif op == OP_CIRCLE:
                pts = []
                seen_groups = None
                for _ in range(2):
                    pt, groups, pos = _read_xy(data, pos)
                    pts.append(pt)
                    seen_groups = groups
                canvas.stream.append(
                    op + "".join(encode_xy(x, y, seen_groups) for x, y in pts)
                )
            elif op == OP_POLY:
                count = decode_value(data[pos : pos + 2])
                pos += 2
                pts = []
                seen_groups = None
                for _ in range(count):
                    pt, groups, pos = _read_xy(data, pos)
                    pts.append(pt)
                    seen_groups = groups
                canvas.stream.append(
                    op
                    + encode_value(count, 2)
                    + "".join(encode_xy(x, y, seen_groups) for x, y in pts)
                )
            elif op == OP_TEXT:
                (x, y), groups, pos = _read_xy(data, pos)
                count = decode_value(data[pos : pos + 2])
                pos += 2
                content = data[pos : pos + count]
                pos += count
                canvas.stream.append(
                    op + encode_xy(x, y, groups) + encode_value(count, 2) + content
                )
            elif op == OP_MACRO_DEF:
                nlen = decode_value(data[pos : pos + 2])
                pos += 2
                name = data[pos : pos + nlen]
                pos += nlen
                mlen = decode_value(data[pos : pos + 2])
                pos += 2
                body = data[pos : pos + mlen]
                pos += mlen
                canvas.macros[name] = Macro(name, body)
                canvas.stream.append(
                    op + encode_value(nlen, 2) + name + encode_value(mlen, 2) + body
                )
            elif op == OP_MACRO_RUN:
                nlen = decode_value(data[pos : pos + 2])
                pos += 2
                name = data[pos : pos + nlen]
                pos += nlen
                if name not in canvas.macros:
                    raise PDIError(f"run of undefined macro {name!r}")
                # expand the macro body inline at decode time
                canvas.stream.append(canvas.macros[name].body)
            elif op == OP_DRCS_LOAD:
                nlen = decode_value(data[pos : pos + 2])
                pos += 2
                name = data[pos : pos + nlen]
                pos += nlen
                total = decode_value(data[pos : pos + 3])
                pos += 3
                payload = data[pos : pos + total]
                pos += total
                glyphs: Dict[int, List[str]] = {}
                p = 0
                while p < len(payload):
                    code = decode_value(payload[p : p + 2])
                    p += 2
                    nrows = decode_value(payload[p : p + 2])
                    p += 2
                    rows = []
                    for _ in range(nrows):
                        bits = decode_value(payload[p : p + 2])
                        p += 2
                        width = decode_value(payload[p : p + 2])
                        p += 2
                        rows.append(format(bits, f"0{width}b"))
                    glyphs[code] = rows
                canvas.fonts[name] = DRCSFont(name, glyphs)
                canvas.stream.append(
                    op + encode_value(nlen, 2) + name + encode_value(total, 3) + payload
                )
            elif op == OP_DRCS_TEXT:
                nlen = decode_value(data[pos : pos + 2])
                pos += 2
                name = data[pos : pos + nlen]
                pos += nlen
                (x, y), groups, pos = _read_xy(data, pos)
                count = decode_value(data[pos : pos + 2])
                pos += 2
                cps = [
                    decode_value(data[pos + 2 * i : pos + 2 * i + 2])
                    for i in range(count)
                ]
                pos += 2 * count
                canvas.stream.append(
                    op
                    + encode_value(nlen, 2)
                    + name
                    + encode_xy(x, y, groups)
                    + encode_value(count, 2)
                    + "".join(encode_value(c, 2) for c in cps)
                )
        return canvas

    def glyph(self, font: str, codepoint: int) -> List[str]:
        """Fetch a DRCS glyph's bit-rows (raises if missing)."""
        try:
            return self.fonts[font].glyphs[codepoint]
        except KeyError:
            raise PDIError(f"glyph {codepoint} not in font {font!r}") from None
