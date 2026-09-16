"""Offline procedural image generator — LEVI's zero-dependency core.

Generates deterministic generative-art compositions from a prompt seed:
layered gradients, glow, geometric shapes, and grain, written as PNG with a
stdlib-only encoder (zlib + struct). No network, no weights, no PIL.

Honest scope: this is procedural art, not photorealistic synthesis. It is
the local-first core — always available, always deterministic — while
photoreal quality comes from the optional Pollinations reference backend
(:mod:`levi.media.pollinations`) or the hardware-gated SD scaffold
(:mod:`levi.media.sd`).
"""

from __future__ import annotations

import hashlib
import math
import random
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_DIR = Path.home() / ".levi" / "media" / "local"

_MAX_DIMENSION = 1024
_MAX_PROMPT_LEN = 2000

STYLES = ("abstract", "photo", "anime", "painting", "product")


def _validate_dimensions(width: int, height: int) -> tuple[int, int]:
    for label, value in (("width", width), ("height", height)):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= _MAX_DIMENSION
        ):
            raise ValueError(
                "%s must be an integer 1-%d, got %r" % (label, _MAX_DIMENSION, value)
            )
    return width, height


def _seed_from(prompt: str, seed: Optional[int]) -> int:
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer or None")
        return seed
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


# ---------------------------------------------------------------------------
# Minimal PNG encoder (truecolor, 8-bit, no interlace)
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", crc & 0xFFFFFFFF)
    )


def encode_png(width: int, height: int, rgb: bytes) -> bytes:
    """Encode raw RGB bytes (width*height*3) as a PNG."""
    if len(rgb) != width * height * 3:
        raise ValueError("rgb buffer length does not match dimensions")
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw += rgb[y * stride : (y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + _png_chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# Generative composition
# ---------------------------------------------------------------------------


def _palette(rng: random.Random, style: str) -> list[tuple[int, int, int]]:
    def rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
        # HSV -> RGB, h,s,v in [0,1]
        i = int(h * 6) % 6
        f = h * 6 - int(h * 6)
        p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
        conv = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
        return tuple(int(c * 255) for c in conv)

    if style == "photo":
        base = rng.uniform(0.05, 0.13)
        return [
            rgb(
                (base + rng.uniform(-0.05, 0.08)) % 1.0,
                rng.uniform(0.15, 0.45),
                rng.uniform(0.25, 0.85),
            )
            for _ in range(5)
        ]
    if style == "anime":
        base = rng.random()
        return [
            rgb(
                (base + i * 0.18) % 1.0,
                rng.uniform(0.65, 0.95),
                rng.uniform(0.55, 0.95),
            )
            for i in range(5)
        ]
    if style == "painting":
        base = rng.uniform(0.0, 0.12)
        return [
            rgb(
                (base + rng.uniform(-0.06, 0.15)) % 1.0,
                rng.uniform(0.45, 0.8),
                rng.uniform(0.3, 0.8),
            )
            for _ in range(5)
        ]
    if style == "product":
        accent = rgb(rng.random(), rng.uniform(0.5, 0.8), rng.uniform(0.5, 0.7))
        light = (245, 244, 242)
        return [light, light, accent, accent, (30, 30, 34)]
    # abstract: vivid full-spectrum
    base = rng.random()
    return [
        rgb((base + i * 0.23) % 1.0, rng.uniform(0.55, 0.95), rng.uniform(0.45, 0.95))
        for i in range(5)
    ]


def _render(width: int, height: int, seed: int, style: str) -> bytes:
    rng = random.Random(seed)
    pal = _palette(rng, style)
    top, bottom, glow_c, shape_c = pal[0], pal[1], pal[2], pal[3:]
    gx, gy = rng.uniform(0.2, 0.8) * width, rng.uniform(0.2, 0.8) * height
    gr = rng.uniform(0.3, 0.7) * max(width, height)

    shapes = []
    n_shapes = 2 if style == "product" else rng.randint(3, 6)
    for _ in range(n_shapes):
        shapes.append(
            {
                "cx": rng.uniform(0, width),
                "cy": rng.uniform(0, height),
                "rx": rng.uniform(0.05, 0.35) * width,
                "ry": rng.uniform(0.05, 0.35) * height,
                "color": rng.choice(shape_c),
                "alpha": rng.uniform(0.25, 0.6),
            }
        )
    grain = 14 if style == "painting" else 7

    out = bytearray(width * height * 3)
    for y in range(height):
        t = y / max(1, height - 1)
        for x in range(width):
            # vertical gradient
            r = top[0] + (bottom[0] - top[0]) * t
            g = top[1] + (bottom[1] - top[1]) * t
            b = top[2] + (bottom[2] - top[2]) * t
            # radial glow
            dx, dy = x - gx, y - gy
            d = math.sqrt(dx * dx + dy * dy) / max(1.0, gr)
            if d < 1.0:
                f = (1.0 - d) ** 2 * 0.55
                r += (glow_c[0] - r) * f
                g += (glow_c[1] - g) * f
                b += (glow_c[2] - b) * f
            # shapes (ellipses, alpha blend)
            for s in shapes:
                ex = (x - s["cx"]) / max(1.0, s["rx"])
                ey = (y - s["cy"]) / max(1.0, s["ry"])
                if ex * ex + ey * ey <= 1.0:
                    a = s["alpha"]
                    c = s["color"]
                    r += (c[0] - r) * a
                    g += (c[1] - g) * a
                    b += (c[2] - b) * a
            # grain
            n = rng.uniform(-grain, grain)
            i = (y * width + x) * 3
            out[i] = max(0, min(255, int(r + n)))
            out[i + 1] = max(0, min(255, int(g + n)))
            out[i + 2] = max(0, min(255, int(b + n)))
    return bytes(out)


@dataclass
class LocalImage:
    prompt: str
    path: Optional[str]
    seed: int
    style: str
    width: int
    height: int

    def format(self) -> str:
        lines = [
            "=== LEVI local procedural image ===",
            f"prompt: {self.prompt[:120]}",
            f"style: {self.style}  seed: {self.seed}  size: {self.width}x{self.height}",
            "(procedural art — deterministic composition, not photoreal synthesis)",
        ]
        if self.path:
            lines.append(f"saved: {self.path}")
        return "\n".join(lines)


def generate(
    prompt: str,
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
    style: str = "abstract",
    save: bool = True,
    save_dir: Optional[Path] = None,
) -> LocalImage:
    """Generate a deterministic procedural PNG. Never touches the network."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    prompt = prompt.strip()[:_MAX_PROMPT_LEN]
    width, height = _validate_dimensions(width, height)
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}, got {style!r}")
    seed = _seed_from(prompt, seed)

    rgb = _render(width, height, seed, style)
    data = encode_png(width, height, rgb)

    path: Optional[str] = None
    if save:
        dest_dir = Path(save_dir) if save_dir else DEFAULT_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"local_{seed % (2**31)}_{style}.png"
        dest.write_bytes(data)
        path = str(dest)
    return LocalImage(
        prompt=prompt, path=path, seed=seed, style=style, width=width, height=height
    )
