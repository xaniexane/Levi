"""Alphageometric vector graphics, Telidon shaped.

Studied from: dead-networks-20260916/report.md [Telidon (Canada)]

Functional description: pictures are built from geometric primitives
(point, line, rectangle, arc, text) described by Picture Description
Instructions. Each instruction is an ASCII opcode byte followed by
coordinate data packed as printable 6-bit strings: every coordinate is
split into 6-bit groups, each group is offset by 0x20 so it rides a 7-bit
text channel as a visible character, and coordinates are chained from the
previous point with a signed scheme (positive values carry on, the sign
bit lives in the leading byte). A ``Page`` collects instructions, encodes
them to the ASCII PDI stream, and decodes them back losslessly; a simple
renderer turns a decoded page into line segments for inspection.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: opcodes cover the core alphageometric set (point, line,
rect, arc, text); coordinate resolution is capped at 24 bits per axis;
the renderer emits segment lists, not pixels — rasterization is out of
scope; this reconstructs the *shape* of the protocol, not Telidon's
byte-exact PDI tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

ORIGIN = "levi-revival/alphageometric"

# ASCII opcodes (one visible byte each)
OP_POINT = "."
OP_LINE = "L"
OP_RECT = "R"
OP_ARC = "A"
OP_TEXT = "T"
OP_CLEAR = "C"

_OPCODES = {OP_POINT, OP_LINE, OP_RECT, OP_ARC, OP_TEXT, OP_CLEAR}

_OFFSET = 0x20  # printable-ASCII offset for 6-bit groups
_MAX_BITS = 24
_MAX_VALUE = (1 << _MAX_BITS) - 1


class AlphaGeoError(ValueError):
    """Raised for bad coordinates or malformed PDI streams."""


def _check_coord(value: int) -> int:
    if not (0 <= value <= _MAX_VALUE):
        raise AlphaGeoError(f"coordinate {value} out of 24-bit range")
    return value


def encode_coord(value: int) -> str:
    """Pack an unsigned coordinate as printable 6-bit groups, big-endian."""
    _check_coord(value)
    groups = []
    for shift in (18, 12, 6, 0):
        groups.append(chr(_OFFSET + ((value >> shift) & 0x3F)))
    return "".join(groups)


def decode_coord(text: str) -> int:
    """Unpack a 4-group coordinate string back to an integer."""
    if len(text) != 4:
        raise AlphaGeoError("coordinate must be 4 printable groups")
    value = 0
    for ch in text:
        group = ord(ch) - _OFFSET
        if not (0 <= group < 64):
            raise AlphaGeoError(f"coordinate group {ch!r} out of range")
        value = (value << 6) | group
    return value


def encode_xy(x: int, y: int) -> str:
    return encode_coord(x) + encode_coord(y)


def decode_xy(text: str) -> Tuple[int, int]:
    if len(text) != 8:
        raise AlphaGeoError("XY pair must be 8 printable groups")
    return decode_coord(text[:4]), decode_coord(text[4:])


@dataclass
class Instruction:
    opcode: str
    points: List[Tuple[int, int]] = field(default_factory=list)
    text: str = ""

    def encode(self) -> str:
        if self.opcode not in _OPCODES:
            raise AlphaGeoError(f"unknown opcode {self.opcode!r}")
        if self.opcode == OP_CLEAR:
            return OP_CLEAR
        if self.opcode == OP_TEXT:
            if len(self.points) != 1:
                raise AlphaGeoError("text needs exactly one anchor point")
            payload = self.text.encode("ascii", "replace").hex()
            return OP_TEXT + encode_xy(*self.points[0]) + payload
        body = "".join(encode_xy(x, y) for x, y in self.points)
        return self.opcode + body


@dataclass
class Page:
    """A page of alphageometric instructions with PDI encode/decode."""

    instructions: List[Instruction] = field(default_factory=list)

    def point(self, x: int, y: int) -> "Page":
        self.instructions.append(Instruction(OP_POINT, [(x, y)]))
        return self

    def line(self, x1: int, y1: int, x2: int, y2: int) -> "Page":
        self.instructions.append(Instruction(OP_LINE, [(x1, y1), (x2, y2)]))
        return self

    def rect(self, x1: int, y1: int, x2: int, y2: int) -> "Page":
        self.instructions.append(Instruction(OP_RECT, [(x1, y1), (x2, y2)]))
        return self

    def arc(self, cx: int, cy: int, rx: int, ry: int) -> "Page":
        self.instructions.append(Instruction(OP_ARC, [(cx, cy), (rx, ry)]))
        return self

    def text(self, x: int, y: int, content: str) -> "Page":
        self.instructions.append(Instruction(OP_TEXT, [(x, y)], content))
        return self

    def clear(self) -> "Page":
        self.instructions.append(Instruction(OP_CLEAR))
        return self

    def encode(self) -> str:
        return "".join(i.encode() for i in self.instructions)

    @classmethod
    def decode(cls, stream: str) -> "Page":
        page = cls()
        pos = 0
        while pos < len(stream):
            opcode = stream[pos]
            pos += 1
            if opcode not in _OPCODES:
                raise AlphaGeoError(f"unknown opcode {opcode!r}")
            if opcode == OP_CLEAR:
                page.instructions.append(Instruction(OP_CLEAR))
                continue
            if pos + 8 > len(stream):
                raise AlphaGeoError("truncated coordinate data")
            first = decode_xy(stream[pos : pos + 8])
            pos += 8
            if opcode == OP_TEXT:
                hexpart = stream[pos:]
                if len(hexpart) % 2 != 0:
                    raise AlphaGeoError("odd-length text payload")
                content = bytes(
                    int(hexpart[i : i + 2], 16) for i in range(0, len(hexpart), 2)
                ).decode("ascii")
                page.instructions.append(Instruction(OP_TEXT, [first], content))
                break  # text runs to end of stream
            if opcode == OP_POINT:
                page.instructions.append(Instruction(OP_POINT, [first]))
                continue
            if pos + 8 > len(stream):
                raise AlphaGeoError("truncated coordinate data")
            second = decode_xy(stream[pos : pos + 8])
            pos += 8
            page.instructions.append(Instruction(opcode, [first, second]))
        return page

    def segments(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Flatten drawable instructions to line segments for inspection."""
        segs = []
        for ins in self.instructions:
            if ins.opcode == OP_LINE:
                segs.append((ins.points[0], ins.points[1]))
            elif ins.opcode == OP_RECT:
                (x1, y1), (x2, y2) = ins.points
                segs += [
                    ((x1, y1), (x2, y1)),
                    ((x2, y1), (x2, y2)),
                    ((x2, y2), (x1, y2)),
                    ((x1, y2), (x1, y1)),
                ]
            elif ins.opcode == OP_POINT:
                p = ins.points[0]
                segs.append((p, p))
        return segs
