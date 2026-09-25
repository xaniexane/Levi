"""NAPLPS Picture Description Instructions: 7-bit-safe ASCII vector opcodes.

Origin: the North American Presentation Level Protocol Syntax (1978, from
Canada's Telidon via the CRC with AT&T's additions — macros, DRCS
downloadable character sets, proportional text), standardized as ANSI
X3.110-1983 / CSA T500-1983 and adopted by CCITT in 1984 as one of three
international videotex protocols. It drove Prodigy and dial-up BBS graphics
into the 1990s. Every drawing command was a single ASCII opcode with XY
coordinates packed as 6-bit strings shifted into the printable ASCII range,
so pictures survived 7-bit channels; SI/SO control codes switched the
terminal between text and graphics modes.

What it is in LEVI: a 7-bit-safe ASCII vector-opcode stream for diagrams.
``pack_xy``/``unpack_xy`` pack each coordinate as three 6-bit bytes in the
printable 0x20-0x5F range; ``NaplpsCodec`` encodes drawing/text opcodes,
switches text/graphics modes with SI/SO, defines reusable macros, and
downloads custom DRCS glyphs — decode expands macros and returns the op
list, round-tripping exactly.

Honesty label: USEFUL PATTERN — the packing, mode switching, macros and
DRCS are the real NAPLPS mechanisms; the opcode set here is a simplified
original sketch, not the full PDI table.

Deny-closed inputs: unknown opcodes, coordinates outside 0..16383,
non-ASCII or empty text, duplicate or undefined macro names, macro bodies
that reference undefined macros, malformed DRCS definitions, and drawing
ops encoded in text mode (or text ops in graphics mode) all raise
ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "Op",
    "NaplpsCodec",
    "pack_xy",
    "unpack_xy",
    "SI",
    "SO",
    "GRAPHICS",
    "TEXT",
    "COORD_MAX",
]

SI = "\x0f"  # shift in:  enter text mode
SO = "\x0e"  # shift out: enter graphics mode

GRAPHICS = "graphics"
TEXT = "text"
COORD_MAX = 0x3FFF  # 14-bit coordinates, packed as 3x 6-bit bytes

# opcode -> (arity in XY pairs, kind)
_OPCODES: dict[str, tuple[int, str]] = {
    "P": (1, "draw"),  # point
    "L": (2, "draw"),  # line
    "R": (2, "draw"),  # rectangle, opposite corners
    "A": (3, "draw"),  # arc: center, start, end
    "T": (1, "text"),  # text at XY
    "C": (0, "color"),  # set color index
    "M": (0, "macro"),  # call macro by name
}


def _pack6(value: int) -> str:
    return "".join(chr(0x20 + ((value >> shift) & 0x3F)) for shift in (12, 6, 0))


def pack_xy(x: int, y: int) -> str:
    """Pack one XY coordinate pair as six printable 7-bit-safe bytes."""
    for name, v in (("x", x), ("y", y)):
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError(f"coordinate {name} must be an int, got {v!r}")
        if not 0 <= v <= COORD_MAX:
            raise ValueError(f"coordinate {name}={v} out of range 0..{COORD_MAX}")
    return _pack6(x) + _pack6(y)


def unpack_xy(data: str, pos: int = 0) -> tuple[int, int, int]:
    """Inverse of pack_xy: return (x, y, next_pos)."""
    if pos + 6 > len(data):
        raise ValueError("truncated coordinate data in stream")
    vals = []
    for i in range(0, 6, 3):
        chunk = data[pos + i : pos + i + 3]
        for ch in chunk:
            if not 0x20 <= ord(ch) <= 0x5F:
                raise ValueError(f"coordinate byte {ch!r} outside 6-bit range")
        vals.append(
            ((ord(chunk[0]) - 0x20) << 12)
            | ((ord(chunk[1]) - 0x20) << 6)
            | (ord(chunk[2]) - 0x20)
        )
    return vals[0], vals[1], pos + 6


@dataclass
class Op:
    opcode: str  # one of "P L R A T C M"
    points: tuple[tuple[int, int], ...] = ()
    text: str = ""  # for T
    color: int = 0  # for C, 0..63
    name: str = ""  # for M, macro name


@dataclass
class _Macro:
    name: str
    ops: list[Op] = field(default_factory=list)


class NaplpsCodec:
    """Encode/decode a 7-bit-safe NAPLPS-style vector opcode stream."""

    def __init__(self) -> None:
        self._mode = TEXT
        self._macros: dict[str, _Macro] = {}
        self._drcs: dict[int, tuple[str, ...]] = {}

    # -- mode ------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    def enter_graphics(self) -> str:
        self._mode = GRAPHICS
        return SO

    def enter_text(self) -> str:
        self._mode = TEXT
        return SI

    # -- macros & DRCS ----------------------------------------------------
    def define_macro(self, name: str, ops: list[Op]) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("macro name must be a non-empty string")
        name = name.strip()
        if not name.isalnum() or len(name) > 8:
            raise ValueError(f"macro name {name!r}: 1-8 alphanumeric chars")
        if name in self._macros:
            raise ValueError(f"duplicate macro: {name!r}")
        if not ops:
            raise ValueError(f"macro {name!r}: body must not be empty")
        for op in ops:
            self._validate_op(op)
            if op.opcode == "M":
                if op.name not in self._macros:
                    raise ValueError(
                        f"macro {name!r}: body calls undefined macro {op.name!r}"
                    )
        self._macros[name] = _Macro(name=name, ops=list(ops))

    def define_glyph(self, code: int, rows: list[str]) -> None:
        """Download one DRCS character: code 0x20..0x7E, bitmap rows of 0/1."""
        if not isinstance(code, int) or isinstance(code, bool):
            raise ValueError(f"glyph code must be an int, got {code!r}")
        if not 0x20 <= code <= 0x7E:
            raise ValueError(f"glyph code {code:#x} outside 0x20..0x7E")
        if code in self._drcs:
            raise ValueError(f"duplicate glyph: {code:#x}")
        if not rows or len(rows) > 16:
            raise ValueError("glyph needs 1..16 rows")
        width = len(rows[0])
        if not 1 <= width <= 16:
            raise ValueError("glyph rows must be 1..16 bits wide")
        for row in rows:
            if len(row) != width or any(c not in "01" for c in row):
                raise ValueError(f"malformed glyph row: {row!r}")
        self._drcs[code] = tuple(rows)

    def glyph(self, code: int) -> Optional[tuple[str, ...]]:
        return self._drcs.get(code)

    # -- encode ------------------------------------------------------------
    def _validate_op(self, op: Op) -> tuple[int, str]:
        spec = _OPCODES.get(op.opcode)
        if spec is None:
            raise ValueError(f"unknown opcode: {op.opcode!r}")
        arity, kind = spec
        if len(op.points) != arity:
            raise ValueError(
                f"opcode {op.opcode!r}: expected {arity} point(s), got {len(op.points)}"
            )
        for x, y in op.points:
            pack_xy(x, y)  # validates range/type
        if op.opcode == "T":
            if not op.text:
                raise ValueError("text op needs non-empty text")
            if any(not 0x20 <= ord(c) <= 0x7E for c in op.text):
                raise ValueError("text must be printable ASCII (7-bit safe)")
            if len(op.text) > 16383:
                raise ValueError("text too long")
        if op.opcode == "C" and not 0 <= op.color <= 63:
            raise ValueError(f"color index {op.color} outside 0..63")
        if op.opcode == "M":
            if not op.name or op.name not in self._macros:
                raise ValueError(f"call to undefined macro: {op.name!r}")
        return arity, kind

    def encode(self, op: Op) -> str:
        arity, kind = self._validate_op(op)
        if kind == "draw" and self._mode != GRAPHICS:
            raise ValueError(
                f"opcode {op.opcode!r} is a drawing op: enter graphics mode first"
            )
        if kind == "text" and self._mode != TEXT:
            raise ValueError(
                f"opcode {op.opcode!r} is a text op: enter text mode first"
            )
        out = op.opcode
        for x, y in op.points:
            out += pack_xy(x, y)
        if op.opcode == "T":
            out += _pack6(len(op.text)) + op.text
        elif op.opcode == "C":
            out += chr(0x20 + op.color)
        elif op.opcode == "M":
            out += chr(0x20 + len(op.name)) + op.name
        return out

    def encode_all(self, ops: list[Op]) -> str:
        return "".join(self.encode(op) for op in ops)

    # -- decode ------------------------------------------------------------
    def decode(self, stream: str) -> list[Op]:
        ops: list[Op] = []
        pos = 0
        mode = TEXT
        while pos < len(stream):
            ch = stream[pos]
            pos += 1
            if ch == SO:
                mode = GRAPHICS
                continue
            if ch == SI:
                mode = TEXT
                continue
            spec = _OPCODES.get(ch)
            if spec is None:
                raise ValueError(f"unknown opcode byte {ch!r} at offset {pos - 1}")
            arity, kind = spec
            if kind == "draw" and mode != GRAPHICS:
                raise ValueError(f"drawing opcode {ch!r} in text mode")
            if kind == "text" and mode != TEXT:
                raise ValueError(f"text opcode {ch!r} in graphics mode")
            points: list[tuple[int, int]] = []
            for _ in range(arity):
                x, y, pos = unpack_xy(stream, pos)
                points.append((x, y))
            text, color, name = "", 0, ""
            if ch == "T":
                if pos + 3 > len(stream):
                    raise ValueError("truncated text length")
                (length,) = (
                    ((ord(stream[pos]) - 0x20) << 12)
                    | ((ord(stream[pos + 1]) - 0x20) << 6)
                    | (ord(stream[pos + 2]) - 0x20),
                )
                pos += 3
                if pos + length > len(stream):
                    raise ValueError("truncated text body")
                text = stream[pos : pos + length]
                pos += length
            elif ch == "C":
                if pos >= len(stream):
                    raise ValueError("truncated color byte")
                color = ord(stream[pos]) - 0x20
                if not 0 <= color <= 63:
                    raise ValueError("color byte outside 0..63")
                pos += 1
            elif ch == "M":
                if pos >= len(stream):
                    raise ValueError("truncated macro name length")
                nlen = ord(stream[pos]) - 0x20
                pos += 1
                if pos + nlen > len(stream):
                    raise ValueError("truncated macro name")
                name = stream[pos : pos + nlen]
                pos += nlen
                if name not in self._macros:
                    raise ValueError(f"stream calls undefined macro {name!r}")
                ops.extend(self._expand_macro(name, stack=(name,)))
                continue
            ops.append(
                Op(
                    opcode=ch,
                    points=tuple(points),
                    text=text,
                    color=color,
                    name=name,
                )
            )
        return ops

    def _expand_macro(self, name: str, stack: tuple[str, ...]) -> list[Op]:
        out: list[Op] = []
        for op in self._macros[name].ops:
            if op.opcode == "M":
                if op.name in stack:
                    raise ValueError(f"recursive macro call: {op.name!r}")
                out.extend(self._expand_macro(op.name, stack + (op.name,)))
            else:
                out.append(op)
        return out
