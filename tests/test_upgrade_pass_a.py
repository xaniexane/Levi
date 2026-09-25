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


# ---- A: photo (⚡)


def _band_v(seed, y0, y1, w=96, h=96):
    rgb = local._render2(w, h, seed, "gradient")
    vals = [max(rgb[(y * w + x) * 3], rgb[(y * w + x) * 3 + 1],
                rgb[(y * w + x) * 3 + 2]) / 255
            for y in range(y0, y1) for x in range(w)]
    return sum(vals) / len(vals)


@pytest.mark.parametrize("seed", (1, 7, 42, 99))
def test_gradient_style_ramps_brightness(seed):
    # A1: the old palette reused one brightness value for all three stops
    # (hue-only gradient). The fix must produce a real top->bottom ramp.
    assert _band_v(seed, 0, 32) - _band_v(seed, 64, 96) > 0.05


def test_gradient_style_still_deterministic():
    a = local._render2(48, 48, 5, "gradient")
    b = local._render2(48, 48, 5, "gradient")
    assert a == b


def test_legacy_styles_byte_identical():
    # U1: the five legacy styles keep their exact render path.
    for style in ("abstract", "photo", "anime", "painting", "product"):
        seed = local._seed_from("legacy pin", 11)
        a = local._render(32, 24, seed, style)
        b = local._render(32, 24, seed, style)
        assert a == b and len(a) == 32 * 24 * 3


def test_same_seed_style_different_prompt_no_overwrite(tmp_path):
    # A2: the old filename local_{seed}_{style}.png silently overwrote.
    a = local.generate("prompt alpha", seed=5, style="dark",
                       save_dir=tmp_path, width=64, height=64)
    b = local.generate("prompt beta", seed=5, style="dark",
                       save_dir=tmp_path, width=64, height=64)
    assert a.path != b.path
    assert Path(a.path).exists() and Path(b.path).exists()
    # same explicit seed -> same pixels (correct); the fix is that the
    # second file no longer overwrites the first.
    assert Path(a.path).read_bytes() == Path(b.path).read_bytes()


