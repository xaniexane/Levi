"""Pre-rendered compressed bitmap pages, CAPTAIN shaped.

Studied from: dead-networks-20260916/report.md [CAPTAIN system (Japan)]

Functional description: pages travel as pre-rendered bi-level bitmaps
rather than character codes — the receiver needs no font, only a decoder.
Each page is coded scanline by scanline with a fax-flavoured scheme: runs
of white/black are coded as two-digit base-40 printable tokens, and a
scanline that repeats the previous line is replaced by a single copy token
('<'). A two-byte magic header carries width and height, so any size page
round-trips. ``to_ascii`` renders a page to terminal text for inspection.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: the run coder is an original fax-*flavoured* scheme, not the
real T.4 modified-Huffman tables; runs cap at 39*40+39 = 1599 pixels and
longer runs are split; a copy token only repeats the *immediately* previous
scanline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/bitmap-pages"

MAGIC = b"CP"  # CAPTAIN Page
_BASE = 40
_COPY_TOKEN = "<"
_MAX_TOKEN_RUN = _BASE * _BASE - 1  # 1599

_ON = "#"
_OFF = " "


class PageError(ValueError):
    """Raised when a page or its coded form is malformed."""


def _encode_run(length: int) -> str:
    """Code a run length as two printable characters (base-40)."""
    if not (1 <= length <= _MAX_TOKEN_RUN):
        raise PageError(f"run length {length} out of range")
    hi = length // _BASE
    lo = length % _BASE
    return chr(ord("0") + hi) + chr(ord("0") + lo)


def _decode_run(pair: str) -> int:
    hi = ord(pair[0]) - ord("0")
    lo = ord(pair[1]) - ord("0")
    if not (0 <= hi < _BASE and 0 <= lo < _BASE):
        raise PageError(f"bad run token {pair!r}")
    length = hi * _BASE + lo
    if length == 0:
        raise PageError("zero-length run")
    return length


@dataclass
class BitmapPage:
    """A bi-level page with fax-flavoured scanline coding."""

    width: int
    height: int
    rows: List[bytes] = field(default_factory=list)  # each row: width bytes 0/1

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise PageError("dimensions must be positive")
        if not self.rows:
            self.rows = [bytes(self.width) for _ in range(self.height)]
        if len(self.rows) != self.height:
            raise PageError("row count does not match height")
        for row in self.rows:
            if len(row) != self.width:
                raise PageError("row width mismatch")
            if any(b not in (0, 1) for b in row):
                raise PageError("row bytes must be 0 or 1")

    @classmethod
    def blank(cls, width: int, height: int) -> "BitmapPage":
        return cls(width, height)

    def set(self, x: int, y: int, value: int = 1) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise PageError(f"pixel ({x}, {y}) out of range")
        row = bytearray(self.rows[y])
        row[x] = 1 if value else 0
        self.rows[y] = bytes(row)

    def _encode_row(self, row: bytes) -> str:
        parts = []
        color = 0
        length = 0
        for px in row:
            if px == color:
                length += 1
                if length == _MAX_TOKEN_RUN:
                    parts.append(("W" if color == 0 else "B") + _encode_run(length))
                    length = 0
            else:
                if length:
                    parts.append(("W" if color == 0 else "B") + _encode_run(length))
                color = px
                length = 1
        if length:
            parts.append(("W" if color == 0 else "B") + _encode_run(length))
        return "".join(parts)

    def encode(self) -> str:
        """Code the page: magic + dims + scanlines (copy-token for repeats)."""
        body = [f"{MAGIC.decode('ascii')} {self.width} {self.height}\n"]
        prev: bytes | None = None
        for row in self.rows:
            if row == prev:
                body.append(_COPY_TOKEN)
            else:
                body.append(self._encode_row(row))
            body.append("\n")
            prev = row
        return "".join(body)

    @classmethod
    def decode(cls, data: str) -> "BitmapPage":
        """Rebuild a page from its coded form."""
        if "\n" not in data:
            raise PageError("page missing header line")
        header, rest = data.split("\n", 1)
        parts = header.split(" ")
        if len(parts) != 3 or parts[0] != MAGIC.decode("ascii"):
            raise PageError("bad page magic")
        try:
            width, height = int(parts[1]), int(parts[2])
        except ValueError:
            raise PageError("bad page dimensions") from None
        if width <= 0 or height <= 0:
            raise PageError("bad page dimensions")
        lines = rest.split("\n")
        rows: List[bytes] = []
        prev: bytes | None = None
        for line in lines:
            if len(rows) == height:
                break
            if line == "":
                continue
            if line == _COPY_TOKEN:
                if prev is None:
                    raise PageError("copy token with no previous line")
                rows.append(prev)
                continue
            if len(line) % 3 != 0:
                raise PageError(f"bad scanline length {len(line)}")
            row = bytearray()
            for i in range(0, len(line), 3):
                color = line[i]
                if color not in ("W", "B"):
                    raise PageError(f"bad run color {color!r}")
                run = _decode_run(line[i + 1 : i + 3])
                row += bytes([1 if color == "B" else 0]) * run
                if len(row) > width:
                    raise PageError("scanline overflows width")
            if len(row) != width:
                raise PageError("scanline underflows width")
            prev = bytes(row)
            rows.append(prev)
        if len(rows) != height:
            raise PageError(f"expected {height} rows, got {len(rows)}")
        return cls(width, height, rows)

    def to_ascii(self) -> str:
        """Render the page as text art (not part of the coded form)."""
        return "\n".join(
            "".join(_ON if px else _OFF for px in row) for row in self.rows
        )

    def ink_ratio(self) -> float:
        """Fraction of black pixels — a cheap compression friendliness hint."""
        total = self.width * self.height
        ink = sum(sum(row) for row in self.rows)
        return ink / total
