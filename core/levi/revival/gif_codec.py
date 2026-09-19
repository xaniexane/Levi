"""LZW-coded 8-bit raster pictures, GIF shaped.

Studied from: dead-networks-20260916/report.md [CompuServe HMI / RLE vector
graphics protocol]

Functional description: 8-bit paletted images are packed into a GIF-shaped
container: the ``GIF89a`` signature, a logical screen descriptor, a global
color table, an image descriptor, and the raster coded as LZW data
sub-blocks. The LZW coder builds its dictionary on the fly from the pixel
bytes: clear code and end-of-information code start the table, codes grow
from min-code-size+1 up to 12 bits, and a clear is re-issued whenever the
table fills. Decoding rebuilds the table in lockstep, so no dictionary
travels with the stream.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: writes the single-image, global-palette, no-extension
subset of the format (no animation, no interlacing, no local palettes, no
Graphic Control Extension); palette limited to 256 entries; code width
caps at 12 bits, which bounds compressible runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/gif-codec"

_SIGNATURE = b"GIF89a"
_MAX_CODE_BITS = 12
_TABLE_LIMIT = 1 << _MAX_CODE_BITS


class GIFError(ValueError):
    """Raised when LZW data or a container is malformed."""


# ---------------------------------------------------------------------------
# LZW codec
# ---------------------------------------------------------------------------


def _code_width(next_code: int, min_code_size: int) -> int:
    """Bit width for the next code given the decoder-side next free code.

    The width is a pure function of ``next_code``: the smallest width that
    fits every code below ``next_code`` (so the KwKwK code ``next_code``
    itself always fits), floored at ``min_code_size + 1`` and capped at 12
    bits. The encoder is always exactly one table entry ahead of the
    decoder at a code boundary, so it calls this with ``next_code - 1``
    and both sides agree on every width.
    """
    width = max(min_code_size + 1, next_code.bit_length())
    return min(width, _MAX_CODE_BITS)


def lzw_compress(data: bytes, min_code_size: int) -> bytes:
    """Compress bytes with GIF-flavoured LZW; returns packed data sub-blocks."""
    if not (1 <= min_code_size <= 8):
        raise GIFError("min_code_size must be 1..8")
    clear = 1 << min_code_size
    eoi = clear + 1
    if any(b >= clear for b in data):
        raise GIFError(
            "pixel values must be below the clear code "
            f"(got value >= {clear} with min_code_size={min_code_size})"
        )

    dictionary: Dict[bytes, int] = {bytes([i]): i for i in range(clear)}
    next_code = eoi + 1

    out_bits: List[tuple] = []

    def emit(code: int) -> None:
        # encoder is one entry ahead: pass next_code - 1
        out_bits.append((code, _code_width(next_code - 1, min_code_size)))

    def reset() -> None:
        nonlocal dictionary, next_code
        dictionary = {bytes([i]): i for i in range(clear)}
        next_code = eoi + 1

    emit(clear)
    w = b""
    for byte in data:
        k = bytes([byte])
        wk = w + k
        if wk in dictionary:
            w = wk
        else:
            emit(dictionary[w])
            if next_code < _TABLE_LIMIT:
                dictionary[wk] = next_code
                next_code += 1
            else:
                emit(clear)
                reset()
            w = k
    if w:
        emit(dictionary[w])
    emit(eoi)

    packed = bytearray()
    acc = 0
    acc_bits = 0
    for code, size in out_bits:
        acc |= code << acc_bits
        acc_bits += size
        while acc_bits >= 8:
            packed.append(acc & 0xFF)
            acc >>= 8
            acc_bits -= 8
    if acc_bits:
        packed.append(acc & 0xFF)
    return _to_subblocks(bytes(packed), min_code_size)


def _to_subblocks(packed: bytes, min_code_size: int) -> bytes:
    chunks = [bytes([min_code_size])]
    for i in range(0, len(packed), 255):
        block = packed[i : i + 255]
        chunks.append(bytes([len(block)]) + block)
    chunks.append(b"\x00")
    return b"".join(chunks)


def lzw_decompress(subblocks: bytes) -> bytes:
    """Inverse of :func:`lzw_compress`; takes the full data-sub-block run."""
    if not subblocks:
        raise GIFError("empty LZW data")
    min_code_size = subblocks[0]
    if not (1 <= min_code_size <= 8):
        raise GIFError("bad min_code_size")
    clear = 1 << min_code_size
    eoi = clear + 1

    packed = bytearray()
    pos = 1
    while True:
        if pos >= len(subblocks):
            raise GIFError("unterminated data sub-blocks")
        size = subblocks[pos]
        pos += 1
        if size == 0:
            break
        packed += subblocks[pos : pos + size]
        pos += size

    table: Dict[int, bytes] = {i: bytes([i]) for i in range(clear)}
    next_code = eoi + 1

    out = bytearray()
    acc = 0
    acc_bits = 0
    idx = 0
    prev = b""

    def read_code() -> int:
        nonlocal acc, acc_bits, idx
        code_size = _code_width(next_code, min_code_size)
        while acc_bits < code_size:
            if idx >= len(packed):
                raise GIFError("truncated LZW stream")
            acc |= packed[idx] << acc_bits
            acc_bits += 8
            idx += 1
        code = acc & ((1 << code_size) - 1)
        acc >>= code_size
        acc_bits -= code_size
        return code

    first = True
    while True:
        code = read_code()
        if code == clear:
            table = {i: bytes([i]) for i in range(clear)}
            next_code = eoi + 1
            first = True
            prev = b""
            continue
        if code == eoi:
            break
        if code in table:
            entry = table[code]
        elif code == next_code and prev:
            entry = prev + prev[:1]  # KwKwK case
        else:
            raise GIFError(f"bad LZW code {code}")
        out += entry
        if not first and next_code < _TABLE_LIMIT:
            table[next_code] = prev + entry[:1]
            next_code += 1
        prev = entry
        first = False
    return bytes(out)


# ---------------------------------------------------------------------------
# GIF-shaped container
# ---------------------------------------------------------------------------


@dataclass
class PalettedImage:
    """An 8-bit image: width, height, pixel indices, and an RGB palette."""

    width: int
    height: int
    pixels: List[int] = field(default_factory=list)
    palette: List[Tuple[int, int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise GIFError("dimensions must be positive")
        if len(self.palette) > 256:
            raise GIFError("palette limited to 256 entries")
        if not self.palette:
            raise GIFError("palette must not be empty")
        if len(self.pixels) != self.width * self.height:
            raise GIFError("pixel count does not match dimensions")
        colors = len(self.palette)
        if any(not (0 <= p < colors) for p in self.pixels):
            raise GIFError("pixel index outside palette")

    def encode(self) -> bytes:
        """Pack into the GIF-shaped single-image container."""
        colors = len(self.palette)
        table_size = 2
        while table_size < colors:
            table_size <<= 1
        # packed byte: GCT flag | color resolution | sort | GCT size
        packed = 0x80 | 0x70 | (table_size.bit_length() - 2)

        out = bytearray()
        out += _SIGNATURE
        out += self.width.to_bytes(2, "little")
        out += self.height.to_bytes(2, "little")
        out += bytes([packed, 0, 0])  # background + aspect
        for r, g, b in self.palette:
            out += bytes([r & 0xFF, g & 0xFF, b & 0xFF])
        for _ in range(table_size - colors):
            out += b"\x00\x00\x00"
        out += b"\x2c"  # image separator
        out += (0).to_bytes(2, "little") * 2
        out += self.width.to_bytes(2, "little")
        out += self.height.to_bytes(2, "little")
        out += b"\x00"  # no local table, not interlaced

        min_code_size = max(2, (colors - 1).bit_length())
        out += lzw_compress(bytes(self.pixels), min_code_size)
        out += b"\x3b"  # trailer
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> "PalettedImage":
        """Unpack a GIF-shaped container produced by :meth:`encode`."""
        if len(data) < 13 or data[:6] != _SIGNATURE:
            raise GIFError("bad signature")
        packed = data[10]
        if not packed & 0x80:
            raise GIFError("no global color table")
        table_size = 2 << (packed & 0x07)
        pos = 13
        palette = []
        for _ in range(table_size):
            palette.append(tuple(data[pos : pos + 3]))
            pos += 3
        if pos >= len(data) or data[pos] != 0x2C:
            raise GIFError("missing image separator")
        pos += 1
        iw = int.from_bytes(data[pos + 4 : pos + 6], "little")
        ih = int.from_bytes(data[pos + 6 : pos + 8], "little")
        if data[pos + 8] & 0x40:
            raise GIFError("interlaced images not supported")
        pos += 9
        # collect the LZW data: min_code_size byte followed by sub-blocks
        end = pos + 1  # skip the min_code_size byte
        while True:
            if end >= len(data):
                raise GIFError("unterminated image data")
            size = data[end]
            end += 1
            if size == 0:
                break
            end += size
            if end > len(data):
                raise GIFError("unterminated image data")
        pixels = list(lzw_decompress(data[pos:end]))
        if len(pixels) != iw * ih:
            raise GIFError("pixel count mismatch")
        return cls(iw, ih, pixels, palette)
