"""Bi-level RLE picture exchange, CompuServe HMI shaped.

Studied from: dead-networks-20260916/report.md [CompuServe HMI / RLE vector
graphics protocol]

Functional description: a bi-level image of fixed 256x192 pixels is coded
as ASCII run pairs riding a 7-bit text channel. Each run is two printable
characters: a color byte ('B' for black, 'W' for white) and a length byte
coding the run length minus one as an offset from '!' (so '!' means a run
of 1, '~' a run of 94). Runs longer than 94 are split. A stream starts with
the two-character header ESC 'G' followed by 'H' (the ESC GH header), then
the run pairs in raster order, and ends with a 'Z' terminator. Decoding
validates the header, expands the pairs back into the 256x192 pixel grid,
and rejects truncated or oversized streams.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: the 256x192 size is fixed (this codec does not carry a
dimension header, matching the studied shape); the length alphabet caps a
single run at 94 pixels; this is a reconstruction of the *shape* of the
protocol, not a byte-exact clone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/rle-image"

WIDTH = 256
HEIGHT = 192
PIXELS = WIDTH * HEIGHT

HEADER = "\x1bGH"  # ESC G H
TERMINATOR = "Z"

BLACK = 1
WHITE = 0

_COLOR_TO_CHAR = {BLACK: "B", WHITE: "W"}
_CHAR_TO_COLOR = {"B": BLACK, "W": WHITE}

_LENGTH_OFFSET = ord("!")
_MAX_RUN = 94  # '~' - '!' + 1


class RLEImageError(ValueError):
    """Raised when an RLE stream is malformed."""


@dataclass
class RLEImage:
    """A bi-level 256x192 picture with RLE encode/decode."""

    pixels: List[int] = field(default_factory=lambda: [WHITE] * PIXELS)

    def __post_init__(self) -> None:
        if len(self.pixels) != PIXELS:
            raise RLEImageError(
                f"image must hold exactly {PIXELS} pixels, got {len(self.pixels)}"
            )
        if any(p not in (BLACK, WHITE) for p in self.pixels):
            raise RLEImageError("pixels must be 0 (white) or 1 (black)")

    @classmethod
    def blank(cls) -> "RLEImage":
        return cls([WHITE] * PIXELS)

    def get(self, x: int, y: int) -> int:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise RLEImageError(f"coordinate ({x}, {y}) out of range")
        return self.pixels[y * WIDTH + x]

    def set(self, x: int, y: int, color: int) -> None:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise RLEImageError(f"coordinate ({x}, {y}) out of range")
        if color not in (BLACK, WHITE):
            raise RLEImageError("color must be 0 or 1")
        self.pixels[y * WIDTH + x] = color

    def runs(self) -> List[tuple]:
        """Collapse the raster into (color, length) runs."""
        out = []
        current = self.pixels[0]
        length = 1
        for px in self.pixels[1:]:
            if px == current and length < _MAX_RUN:
                length += 1
            else:
                out.append((current, length))
                current, length = px, 1
        out.append((current, length))
        return out

    def encode(self) -> str:
        """Encode to the ASCII RLE stream (header + pairs + terminator)."""
        parts = [HEADER]
        for color, length in self.runs():
            remaining = length
            while remaining > 0:
                chunk = min(remaining, _MAX_RUN)
                parts.append(_COLOR_TO_CHAR[color])
                parts.append(chr(_LENGTH_OFFSET + chunk - 1))
                remaining -= chunk
        parts.append(TERMINATOR)
        return "".join(parts)

    @classmethod
    def decode(cls, stream: str) -> "RLEImage":
        """Decode an ASCII RLE stream back into an image."""
        if not stream.startswith(HEADER):
            raise RLEImageError("stream missing ESC GH header")
        body = stream[len(HEADER) :]
        if not body.endswith(TERMINATOR):
            raise RLEImageError("stream missing terminator")
        body = body[: -len(TERMINATOR)]
        if len(body) % 2 != 0:
            raise RLEImageError("run body has odd length")

        pixels: List[int] = []
        for i in range(0, len(body), 2):
            color_char = body[i]
            length_char = body[i + 1]
            if color_char not in _CHAR_TO_COLOR:
                raise RLEImageError(f"bad color byte {color_char!r}")
            code = ord(length_char) - _LENGTH_OFFSET
            if not (0 <= code < _MAX_RUN):
                raise RLEImageError(f"bad length byte {length_char!r}")
            pixels.extend([_CHAR_TO_COLOR[color_char]] * (code + 1))
            if len(pixels) > PIXELS:
                raise RLEImageError("stream overflows the 256x192 grid")
        if len(pixels) != PIXELS:
            raise RLEImageError(f"stream covers {len(pixels)} pixels, need {PIXELS}")
        return cls(pixels)

    def to_ascii(self, cols: int = 64) -> str:
        """Render a downsampled text preview (not part of the wire format)."""
        step_x = max(1, WIDTH // cols)
        step_y = max(1, HEIGHT // (cols // 2))
        lines = []
        for y in range(0, HEIGHT, step_y):
            row = []
            for x in range(0, WIDTH, step_x):
                row.append("#" if self.pixels[y * WIDTH + x] else ".")
            lines.append("".join(row))
        return "\n".join(lines)
