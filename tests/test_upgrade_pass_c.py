"""Upgrade-pass proof tests (⚡): strengthen/refine/improve over the four
recent media builds, with Alpha as the critic.

Laws:
  U1 no regression — pre-existing deterministic outputs unchanged
      (legacy styles, ASCII L1-L6, video receipts).
  U2 no fakes — every new feature proven by a test that fails if faked.
  U3 Alpha judges — alpha_critique returns substrate-labeled verdicts.
  U4 bundle v1 stays forward-compatible.
"""

import json
import re
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from levi.media import ascii_art, local, refine, video
from levi.knowledge.video_learn import analyze, engines

TMP = Path("/tmp")


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", *args],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   timeout=120, check=True)


def _gray_png(width, height, rows):
    def chunk(t, data):
        c = struct.pack(">I", len(data)) + t + data
        return c + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# ---- C: ascii (⚡)


def test_color_capture_and_ansi_render():
    # C1: color is display-only — the chars must be identical either way.
    rgb = bytes([200, 30, 10, 10, 200, 30, 10, 10, 200] * 48)
    color = ascii_art.image_to_ascii(rgb, 12, 12, cols=8, capture_color=True)
    plain = ascii_art.image_to_ascii(rgb, 12, 12, cols=8)
    assert color.lines == plain.lines  # same composition
    assert color.colors is not None
    assert len(color.colors) == color.rows * color.cols
    assert all(len(t) == 3 and all(0 <= v <= 255 for v in t)
               for t in color.colors)
    assert plain.colors is None
    ansi = ascii_art.to_ansi(color)
    assert "\x1b[38;2;" in ansi and ansi.endswith("\x1b[0m")
    stripped = re.sub(r"\x1b\[[0-9;]*m", "", ansi)
    assert stripped == color.text()  # escapes add nothing to the art
    assert "\x1b" not in ascii_art.to_ansi(plain)  # monochrome stays clean


def test_color_capture_is_deterministic():
    rgb = bytes([i % 256 for i in range(48 * 48 * 3)])
    a = ascii_art.image_to_ascii(rgb, 48, 48, cols=24, capture_color=True)
    b = ascii_art.image_to_ascii(rgb, 48, 48, cols=24, capture_color=True)
    assert a.colors == b.colors and a.lines == b.lines


def test_decode_grayscale_png():
    # C2: 8-bit grayscale (color type 0) decodes, expanded to RGB.
    png = _gray_png(4, 2, [[10, 20, 30, 40], [50, 60, 70, 80]])
    w, h, px = ascii_art.decode_png(png)
    assert (w, h) == (4, 2)
    assert px[0:3] == bytes([10, 10, 10])
    assert px[3:6] == bytes([20, 20, 20])
    assert px[-3:] == bytes([80, 80, 80])


def test_decode_palette_png_still_refused():
    def chunk(t, data):
        c = struct.pack(">I", len(data)) + t + data
        return c + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 3, 0, 0, 0)  # color type 3
    raw = b"\x00\x00\x01" * 2
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    with pytest.raises(ascii_art.PngDecodeError):
        ascii_art.decode_png(png)


def test_bundle_v1_still_compatible():
    # U4: bundles packed before this pass (no colors field) still unpack.
    rgb = bytes([128] * 32 * 32 * 3)
    b = ascii_art.compress_pixels(rgb, 32, 32, prompt="v1", seed=3)
    packed = ascii_art.pack(b)
    back = ascii_art.unpack(packed)
    assert back.prompt == "v1" and back.seed == 3
    r1 = ascii_art.regenerate(b, scale=4)
    r2 = ascii_art.regenerate(back, scale=4)
    assert r1 == r2  # L1 untouched


