"""Offline procedural image generator — LEVI's zero-dependency core.

Generates deterministic generative-art compositions from a prompt seed:
layered gradients, glow, geometric shapes, and grain, written as PNG with a
stdlib-only encoder (zlib + struct). No network, no weights, no PIL.

Honest scope: this is procedural art, not photorealistic synthesis. It is
the local-first core — always available, always deterministic — while
photoreal quality comes from the optional Pollinations reference backend
(:mod:`levi.media.pollinations`) or the hardware-gated SD scaffold
(:mod:`levi.media.sd`).

Extended composition styles (still procedural, still deterministic):

* ``gradient`` — smooth multi-stop gradient backdrop with vignette; built
  for thumbnail backgrounds and lower-third plates.
* ``dark`` — dark-mode abstract; keeps the luminance low so overlaid text
  stays readable.
* ``poster`` — bold flat color bands with one strong graphic bar; poster
  and cover layouts.
* ``mockup-device`` / ``mockup-backdrop`` — product-mockup templates via
  :func:`mockup`: plain backdrop, soft drop shadow, and either a device
  frame (phone) or a plain product card.

Text-safe zones: :func:`text_safe_zone` returns the overlay-safe rectangle
for a ``"top"`` or ``"bottom"`` band, and ``generate(..., caption_band=...)``
darkens that band so burned-in captions stay legible. What the function
draws is what you get — there is no font rendering here; captions are
burned in later by :mod:`levi.media.video`.
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

STYLES = (
    "abstract",
    "photo",
    "anime",
    "painting",
    "product",
    "gradient",
    "dark",
    "poster",
    "mockup-device",
    "mockup-backdrop",
)

MOCKUP_TEMPLATES = ("device", "backdrop")
_MOCKUP_STYLE = {"device": "mockup-device", "backdrop": "mockup-backdrop"}

# Styles rendered by the v2 compositor (new primitives: bands, vignette,
# rounded rects, soft shadows). The original five styles keep their exact
# legacy render path so their output never changes.
_V2_STYLES = ("gradient", "dark", "poster", "mockup-device", "mockup-backdrop")


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


# ---------------------------------------------------------------------------
# v2 compositor — extended styles (bands, vignette, rounded rects, shadows)
# ---------------------------------------------------------------------------


def _palette2(rng: random.Random, style: str) -> list[tuple[int, int, int]]:
    def rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
        i = int(h * 6) % 6
        f = h * 6 - int(h * 6)
        p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
        conv = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
        return tuple(int(c * 255) for c in conv)

    if style == "gradient":
        base = rng.random()
        # ⚡ upgrade pass: brightness used to be drawn once and reused for all
        # three stops, so gradients were hue-only. Vary it per stop so the
        # gradient ramps top -> bottom.
        v_hi = rng.uniform(0.55, 0.78)
        v_lo = rng.uniform(0.25, 0.42)
        stops = [
            rgb((base + i * 0.09) % 1.0, rng.uniform(0.35, 0.6), v)
            for i, v in enumerate((v_hi, (v_hi + v_lo) / 2, v_lo))
        ]
        return stops
    if style == "dark":
        base = rng.random()
        return [
            rgb(
                (base + i * 0.21) % 1.0,
                rng.uniform(0.4, 0.7),
                rng.uniform(0.05, 0.28),
            )
            for i in range(5)
        ]
    if style == "poster":
        base = rng.random()
        return [
            rgb(
                (base + i * 0.25) % 1.0,
                rng.uniform(0.7, 0.95),
                rng.uniform(0.5, 0.9),
            )
            for i in range(4)
        ]
    if style in ("mockup-device", "mockup-backdrop"):
        accent = rgb(rng.random(), rng.uniform(0.45, 0.7), rng.uniform(0.45, 0.65))
        return [
            (246, 245, 243),  # backdrop light
            (232, 230, 227),  # backdrop shade
            accent,  # accent
            (28, 28, 32),  # bezel / ink
            (255, 255, 255),  # card / screen
        ]
    raise ValueError(f"unknown v2 style {style!r}")


def _in_rounded_rect(
    x: float, y: float, cx: float, cy: float, w: float, h: float, r: float
) -> bool:
    dx = abs(x - cx) - (w / 2 - r)
    dy = abs(y - cy) - (h / 2 - r)
    if dx <= 0:
        return dy <= 0
    if dy <= 0:
        return True
    return dx * dx + dy * dy <= r * r


def _render2(width: int, height: int, seed: int, style: str) -> bytes:
    # Domain-separated seed: v2 styles never collide with the legacy path.
    rng = random.Random(seed ^ 0x5EED01)
    pal = _palette2(rng, style)
    out = bytearray(width * height * 3)

    if style == "gradient":
        top, mid, bottom = pal[0], pal[1], pal[2]
        vig = rng.uniform(0.25, 0.45)
        grain = 5
        cx, cy = width / 2, height / 2
        maxd = math.hypot(cx, cy)
        for y in range(height):
            t = y / max(1, height - 1)
            if t < 0.5:
                f = t * 2
                r = top[0] + (mid[0] - top[0]) * f
                g = top[1] + (mid[1] - top[1]) * f
                b = top[2] + (mid[2] - top[2]) * f
            else:
                f = (t - 0.5) * 2
                r = mid[0] + (bottom[0] - mid[0]) * f
                g = mid[1] + (bottom[1] - mid[1]) * f
                b = mid[2] + (bottom[2] - mid[2]) * f
            for x in range(width):
                d = math.hypot(x - cx, y - cy) / maxd
                v = 1.0 - vig * d * d
                n = rng.uniform(-grain, grain)
                i = (y * width + x) * 3
                out[i] = max(0, min(255, int(r * v + n)))
                out[i + 1] = max(0, min(255, int(g * v + n)))
                out[i + 2] = max(0, min(255, int(b * v + n)))
        return bytes(out)

    if style == "dark":
        top, bottom = pal[0], pal[1]
        shapes = [
            {
                "cx": rng.uniform(0, width),
                "cy": rng.uniform(0, height),
                "rx": rng.uniform(0.1, 0.4) * width,
                "ry": rng.uniform(0.1, 0.4) * height,
                "color": rng.choice(pal[2:]),
                "alpha": rng.uniform(0.15, 0.35),
            }
            for _ in range(rng.randint(3, 5))
        ]
        grain = 7
        for y in range(height):
            t = y / max(1, height - 1)
            for x in range(width):
                r = top[0] + (bottom[0] - top[0]) * t
                g = top[1] + (bottom[1] - top[1]) * t
                b = top[2] + (bottom[2] - top[2]) * t
                for s in shapes:
                    ex = (x - s["cx"]) / max(1.0, s["rx"])
                    ey = (y - s["cy"]) / max(1.0, s["ry"])
                    if ex * ex + ey * ey <= 1.0:
                        a = s["alpha"]
                        c = s["color"]
                        r += (c[0] - r) * a
                        g += (c[1] - g) * a
                        b += (c[2] - b) * a
                n = rng.uniform(-grain, grain)
                i = (y * width + x) * 3
                out[i] = max(0, min(255, int(r + n)))
                out[i + 1] = max(0, min(255, int(g + n)))
                out[i + 2] = max(0, min(255, int(b + n)))
        return bytes(out)

    if style == "poster":
        nbands = rng.choice((3, 4))
        band_h = height / nbands
        slope = rng.uniform(-0.6, 0.6)
        thick = rng.uniform(0.04, 0.09) * height
        off = rng.uniform(0, height)
        bar_c = pal[-1]
        for y in range(height):
            band = min(nbands - 1, int(y / band_h))
            c = pal[band % len(pal)]
            for x in range(width):
                # one bold diagonal graphic bar across the bands
                on_bar = abs(x - (y * slope + off)) < thick
                cc = bar_c if on_bar else c
                i = (y * width + x) * 3
                out[i], out[i + 1], out[i + 2] = cc
        return bytes(out)

    # mockup-device / mockup-backdrop: plain backdrop, soft shadow, product
    light, shade, accent, ink, card = pal
    cx, cy = width / 2, height / 2
    # product rect dims
    if style == "mockup-device":
        pw, ph = width * 0.42, height * 0.66
    else:
        pw, ph = width * 0.56, height * 0.44
    py = height * 0.46
    sh_w, sh_h = pw * 1.15, height * 0.07
    sh_cy = py + ph / 2 + sh_h * 0.7
    for y in range(height):
        t = y / max(1, height - 1)
        for x in range(width):
            r = light[0] + (shade[0] - light[0]) * t
            g = light[1] + (shade[1] - light[1]) * t
            b = light[2] + (shade[2] - light[2]) * t
            # soft drop shadow (ellipse, radial falloff toward black)
            ex = (x - cx) / max(1.0, sh_w / 2)
            ey = (y - sh_cy) / max(1.0, sh_h / 2)
            e = ex * ex + ey * ey
            if e < 1.0:
                a = (1.0 - e) ** 2 * 0.38
                r += (40 - r) * a
                g += (40 - g) * a
                b += (44 - b) * a
            i = (y * width + x) * 3
            out[i] = max(0, min(255, int(r)))
            out[i + 1] = max(0, min(255, int(g)))
            out[i + 2] = max(0, min(255, int(b)))
    # product shape on top
    rad = min(pw, ph) * 0.08
    for y in range(height):
        for x in range(width):
            if not _in_rounded_rect(x, y, cx, py, pw, ph, rad):
                continue
            i = (y * width + x) * 3
            if style == "mockup-device":
                # bezel: dark frame, lighter screen inset, accent bar, camera dot
                inset = min(pw, ph) * 0.06
                if _in_rounded_rect(x, y, cx, py, pw - inset * 2, ph - inset * 2, rad * 0.7):
                    c = card
                else:
                    c = ink
                out[i], out[i + 1], out[i + 2] = c
                # camera dot near top
                if math.hypot(x - cx, y - (py - ph / 2 + inset * 1.2)) < inset * 0.35:
                    out[i] = out[i + 1] = out[i + 2] = 90
                # accent bar across the screen middle
                if abs(y - py) < ph * 0.02 and abs(x - cx) < pw * 0.3:
                    out[i], out[i + 1], out[i + 2] = accent
            else:
                # plain card: light face, thin ink border, accent header band
                border = max(2.0, min(width, height) * 0.004)
                inner = _in_rounded_rect(
                    x, y, cx, py, pw - border * 2, ph - border * 2, rad * 0.7
                )
                if not inner:
                    out[i], out[i + 1], out[i + 2] = ink
                elif y < py - ph / 2 + ph * 0.22:
                    out[i], out[i + 1], out[i + 2] = accent
                else:
                    out[i], out[i + 1], out[i + 2] = card
    return bytes(out)


# ---------------------------------------------------------------------------
# Text-safe zones + product mockups
# ---------------------------------------------------------------------------


def text_safe_zone(
    width: int,
    height: int,
    position: str = "bottom",
    ratio: float = 0.28,
    margin: float = 0.04,
) -> dict:
    """Overlay-safe rectangle for burned-in captions.

    Returns ``{"x","y","w","h","position"}`` in pixels. ``position`` is
    ``"top"`` or ``"bottom"``; ``ratio`` is the band height as a fraction
    of the frame; ``margin`` insets the band from the frame edges.

    Dimensions are validated independently of the generator's 1024px cap —
    safe zones apply to video frames (e.g. 1080x1920) too.
    """
    for label, value in (("width", width), ("height", height)):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 8192
        ):
            raise ValueError(
                "%s must be an integer 1-8192, got %r" % (label, value)
            )
    if position not in ("top", "bottom"):
        raise ValueError(f"position must be 'top' or 'bottom', got {position!r}")
    if not 0.05 <= ratio <= 0.6:
        raise ValueError(f"ratio must be 0.05-0.6, got {ratio!r}")
    if not 0.0 <= margin <= 0.2:
        raise ValueError(f"margin must be 0.0-0.2, got {margin!r}")
    mx = int(width * margin)
    my = int(height * margin)
    band_h = int(height * ratio)
    w = width - 2 * mx
    y = my if position == "top" else height - my - band_h
    return {"x": mx, "y": y, "w": w, "h": band_h, "position": position}


def _darken_band(rgb: bytes, width: int, height: int, zone: dict, factor: float = 0.42) -> bytes:
    out = bytearray(rgb)
    x0, y0 = zone["x"], zone["y"]
    x1 = min(width, x0 + zone["w"])
    y1 = min(height, y0 + zone["h"])
    for y in range(max(0, y0), y1):
        for x in range(max(0, x0), x1):
            i = (y * width + x) * 3
            out[i] = int(out[i] * factor)
            out[i + 1] = int(out[i + 1] * factor)
            out[i + 2] = int(out[i + 2] * factor)
    return bytes(out)


def mockup(
    prompt: str,
    template: str = "device",
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
    save: bool = True,
    save_dir: Optional[Path] = None,
) -> "LocalImage":
    """Product-mockup template render.

    ``template="device"`` draws a phone-style device frame; ``"backdrop"``
    draws a plain product card. Both sit on a plain backdrop with a soft
    drop shadow — a layout plate, not a product photo.
    """
    if template not in MOCKUP_TEMPLATES:
        raise ValueError(
            f"template must be one of {MOCKUP_TEMPLATES}, got {template!r}"
        )
    return generate(
        prompt,
        width=width,
        height=height,
        seed=seed,
        style=_MOCKUP_STYLE[template],
        save=save,
        save_dir=save_dir,
    )


@dataclass
class LocalImage:
    prompt: str
    path: Optional[str]
    seed: int
    style: str
    width: int
    height: int
    safe_zone: Optional[dict] = None

    def format(self) -> str:
        lines = [
            "=== LEVI local procedural image ===",
            f"prompt: {self.prompt[:120]}",
            f"style: {self.style}  seed: {self.seed}  size: {self.width}x{self.height}",
            "(procedural art — deterministic composition, not photoreal synthesis)",
        ]
        if self.safe_zone:
            z = self.safe_zone
            lines.append(
                f"caption band darkened: {z['position']} "
                f"({z['x']},{z['y']} {z['w']}x{z['h']})"
            )
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
    caption_band: Optional[str] = None,
) -> LocalImage:
    """Generate a deterministic procedural PNG. Never touches the network.

    ``caption_band`` (``"top"``/``"bottom"``/None) darkens the text-safe
    zone so burned-in captions stay legible; the zone rect is recorded on
    the returned image.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    prompt = prompt.strip()[:_MAX_PROMPT_LEN]
    width, height = _validate_dimensions(width, height)
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}, got {style!r}")
    if caption_band is not None and caption_band not in ("top", "bottom"):
        raise ValueError(
            f"caption_band must be 'top', 'bottom', or None, got {caption_band!r}"
        )
    seed = _seed_from(prompt, seed)

    if style in _V2_STYLES:
        rgb = _render2(width, height, seed, style)
    else:
        rgb = _render(width, height, seed, style)

    zone: Optional[dict] = None
    if caption_band is not None:
        zone = text_safe_zone(width, height, position=caption_band)
        rgb = _darken_band(rgb, width, height, zone)

    data = encode_png(width, height, rgb)

    path: Optional[str] = None
    if save:
        dest_dir = Path(save_dir) if save_dir else DEFAULT_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        # ⚡ upgrade pass: the filename used to be local_{seed}_{style}.png,
        # so two different prompts with the same seed+style silently
        # overwrote each other. The prompt hash makes it collision-proof.
        ph = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
        dest = dest_dir / f"local_{seed % (2**31)}_{style}_{ph}.png"
        dest.write_bytes(data)
        path = str(dest)
    return LocalImage(
        prompt=prompt,
        path=path,
        seed=seed,
        style=style,
        width=width,
        height=height,
        safe_zone=zone,
    )
