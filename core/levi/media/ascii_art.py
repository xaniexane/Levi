"""ASCII compression pipeline for LEVI media.

Chauncey's idea, implemented as specified: images are stored as compact
ASCII art (plus seed/params/hash), then regenerated or remixed later from
the ASCII. A thumbs-down selection loop lets a user cruise through
candidates: thumbs-down on a picture offers a fresh set of alternatives of
the desired picture to pick from.

LAWS (invariants — declared before implementation, proved by tests):
  L1 determinism: same bundle + same params -> byte-identical PNG output.
  L2 compression: packed bundle is smaller than the source PNG it came from.
  L3 lossless decode: decode_png(encode_png(rgb)) == rgb, byte for byte.
  L4 fresh alternatives: thumbs_down() always returns exactly per_round NEW
     candidates; a rejected id never reappears in the same session.
  L5 honest failure: corrupt PNGs, malformed bundles, bad params raise typed
     errors. No silent garbage, no network, no Pillow — stdlib only.
  L6 measured fidelity: regeneration is grayscale and downsampled by design;
     the similarity score is computed and reported, never claimed.

Honest limits: this is lossy compression (color -> grayscale luminance,
resolution -> cols x rows characters). It stores the *composition*, not the
pixels. Regeneration reproduces the composition faithfully; it does not
recover lost color or detail.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical charset: index 0 = darkest, last = lightest. 10 levels.
CHARSET_DENSE = "@%#*+=-:. "
#: Higher-contrast variant for remixing.
CHARSET_BLOCKS = "\u2588\u2593\u2592\u2591:. "
#: Terminal-friendly minimal variant.
CHARSET_MINIMAL = "@#*+=-:. "

#: Character cells are ~twice as tall as wide; this keeps aspect honest.
CELL_ASPECT = 0.5

BUNDLE_VERSION = 1
MIN_COLS, MAX_COLS = 8, 256
MIN_SCALE, MAX_SCALE = 1, 32


class PngDecodeError(ValueError):
    """Raised when PNG bytes cannot be honestly decoded."""


class BundleError(ValueError):
    """Raised when an ASCII bundle is malformed or fails validation."""


class CurateError(ValueError):
    """Raised for thumbs-loop misuse (unknown id, double pick, ...)."""


# ---------------------------------------------------------------------------
# Minimal stdlib PNG decoder (8-bit RGB / RGBA, filters 0-4)
# ---------------------------------------------------------------------------

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(data: bytes) -> Tuple[int, int, bytes]:
    """Decode PNG bytes -> (width, height, raw RGB bytes).

    Supports 8-bit color types 0 (grayscale, expanded to RGB), 2 (RGB)
    and 6 (RGBA; alpha is dropped). Verifies the signature and every chunk
    CRC; fails closed otherwise.
    """
    if not isinstance(data, (bytes, bytearray)) or data[:8] != _PNG_SIG:
        raise PngDecodeError("not a PNG (bad signature)")
    pos, width, height, bit_depth, color_type = 8, None, None, None, None
    idat = bytearray()
    seen_iend = False
    n = len(data)
    while pos + 8 <= n:
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        if zlib.crc32(ctype + cdata) & 0xFFFFFFFF != crc:
            raise PngDecodeError(f"chunk {ctype!r} CRC mismatch (corrupt file)")
        if ctype == b"IHDR":
            if width is not None:
                raise PngDecodeError("duplicate IHDR")
            width, height, bit_depth, color_type, comp, filt, inter = struct.unpack(
                ">IIBBBBB", cdata
            )
            if bit_depth != 8 or color_type not in (0, 2, 6):
                raise PngDecodeError(
                    f"unsupported PNG: bit_depth={bit_depth} color_type={color_type} "
                    "(need 8-bit grayscale/RGB/RGBA)"
                )
            if comp != 0 or filt != 0 or inter != 0:
                raise PngDecodeError("unsupported PNG compression/filter/interlace")
            if width <= 0 or height <= 0 or width * height > 100_000_000:
                raise PngDecodeError(f"refusing absurd dimensions {width}x{height}")
        elif ctype == b"IDAT":
            idat += cdata
        elif ctype == b"IEND":
            seen_iend = True
            break
        pos += 12 + length
    if width is None:
        raise PngDecodeError("missing IHDR")
    if not seen_iend:
        raise PngDecodeError("missing IEND (truncated file)")
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as e:
        raise PngDecodeError(f"IDAT decompression failed: {e}") from e

    bpp = {0: 1, 2: 3, 6: 4}[color_type]
    stride = width * bpp
    expected = height * (1 + stride)
    if len(raw) != expected:
        raise PngDecodeError(
            f"scanline size mismatch: got {len(raw)}, expected {expected}"
        )
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        f = raw[p]
        p += 1
        cur = bytearray(raw[p : p + stride])
        p += stride
        if f == 1:  # Sub
            for i in range(bpp, stride):
                cur[i] = (cur[i] + cur[i - bpp]) & 0xFF
        elif f == 2:  # Up
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 0xFF
        elif f == 3:  # Average
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:  # Paeth
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + _paeth(a, b, c)) & 0xFF
        elif f != 0:
            raise PngDecodeError(f"unknown filter type {f}")
        if bpp == 3:
            out[y * width * 3 : (y + 1) * width * 3] = cur
        elif bpp == 4:  # strip alpha
            dst = y * width * 3
            for x in range(width):
                s = x * 4
                out[dst + x * 3 : dst + x * 3 + 3] = cur[s : s + 3]
        else:  # bpp == 1: expand grayscale to RGB
            dst = y * width * 3
            for x in range(width):
                v = cur[x]
                out[dst + x * 3] = out[dst + x * 3 + 1] = out[dst + x * 3 + 2] = v
        prev = cur
    return width, height, bytes(out)


# ---------------------------------------------------------------------------
# ASCII encode / decode
# ---------------------------------------------------------------------------


def _luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _validate_grid(cols: int, charset: str) -> None:
    if not isinstance(cols, int) or not (MIN_COLS <= cols <= MAX_COLS):
        raise ValueError(f"cols must be an int in [{MIN_COLS},{MAX_COLS}]")
    if not charset or len(set(charset)) < 2:
        raise ValueError("charset needs at least 2 distinct characters")
    if any(ord(c) > 0xFFFF for c in charset):
        raise ValueError("charset must be BMP characters")


@dataclass(frozen=True)
class AsciiArt:
    cols: int
    rows: int
    charset: str
    lines: Tuple[str, ...]
    # ⚡ upgrade: optional per-cell mean RGB, captured by
    # image_to_ascii(..., capture_color=True). Display-only — never stored
    # in the bundle (bundles stay v1 grayscale), so L1/L2 are untouched.
    colors: Optional[Tuple[Tuple[int, int, int], ...]] = None

    def __post_init__(self) -> None:
        if len(self.lines) != self.rows or any(len(l) != self.cols for l in self.lines):
            raise BundleError("art lines do not match cols x rows")
        if self.colors is not None and len(self.colors) != self.rows * self.cols:
            raise BundleError("colors must have one RGB triple per cell")

    def text(self) -> str:
        return "\n".join(self.lines)


def to_ansi(art: AsciiArt) -> str:
    """Render ASCII art for a terminal, with 24-bit color when the art was
    captured with ``capture_color=True``. Plain monochrome otherwise."""
    out: List[str] = []
    for r, line in enumerate(art.lines):
        parts: List[str] = []
        for c, ch in enumerate(line):
            if art.colors is not None:
                cr, cg, cb = art.colors[r * art.cols + c]
                parts.append(f"\x1b[38;2;{cr};{cg};{cb}m{ch}")
            else:
                parts.append(ch)
        if art.colors is not None:
            parts.append("\x1b[0m")
        out.append("".join(parts))
    return "\n".join(out)


def image_to_ascii(
    rgb: bytes,
    width: int,
    height: int,
    cols: int = 80,
    charset: str = CHARSET_DENSE,
    capture_color: bool = False,
) -> AsciiArt:
    """Compress a raw RGB buffer to ASCII art (the storage form).

    ``capture_color=True`` also records the per-cell mean RGB so
    :func:`to_ansi` can render a color terminal view. The colors are
    display-only metadata on the AsciiArt object — they never enter the
    bundle, so compression ratios and regeneration are unchanged.
    """
    _validate_grid(cols, charset)
    if len(rgb) != width * height * 3:
        raise ValueError("rgb buffer length does not match dimensions")
    n = len(charset)
    rows = max(1, int(round(cols * height / width * CELL_ASPECT)))
    lines: List[str] = []
    colors: List[Tuple[int, int, int]] = []
    for r in range(rows):
        y0 = r * height // rows
        y1 = max(y0 + 1, (r + 1) * height // rows)
        chars: List[str] = []
        for c in range(cols):
            x0 = c * width // cols
            x1 = max(x0 + 1, (c + 1) * width // cols)
            total = 0.0
            sr = sg = sb = 0
            count = 0
            for y in range(y0, y1):
                base = y * width * 3
                for x in range(x0, x1):
                    o = base + x * 3
                    rr, gg, bb = rgb[o], rgb[o + 1], rgb[o + 2]
                    total += _luminance(rr, gg, bb)
                    sr += rr
                    sg += gg
                    sb += bb
                    count += 1
            lum = total / count
            idx = min(n - 1, int(lum * n / 256))
            chars.append(charset[idx])
            if capture_color:
                colors.append((sr // count, sg // count, sb // count))
        lines.append("".join(chars))
    return AsciiArt(
        cols=cols,
        rows=rows,
        charset=charset,
        lines=tuple(lines),
        colors=tuple(colors) if capture_color else None,
    )


def _char_level(ch: str, charset: str) -> float:
    return charset.index(ch) / (len(charset) - 1)


def ascii_to_rgb(art: AsciiArt, scale: int = 8) -> Tuple[int, int, bytes]:
    """Regenerate raw RGB bytes from ASCII art (the retrieval form).

    Each character becomes a scale x scale block of its grayscale level.
    Deterministic by construction: same art + scale -> identical bytes.
    """
    if not isinstance(scale, int) or not (MIN_SCALE <= scale <= MAX_SCALE):
        raise ValueError(f"scale must be an int in [{MIN_SCALE},{MAX_SCALE}]")
    width, height = art.cols * scale, art.rows * scale
    out = bytearray(width * height * 3)
    for r, line in enumerate(art.lines):
        for c, ch in enumerate(line):
            gray = int(round(_char_level(ch, art.charset) * 255))
            for dy in range(scale):
                base = ((r * scale + dy) * width + c * scale) * 3
                for dx in range(scale):
                    o = base + dx * 3
                    out[o] = out[o + 1] = out[o + 2] = gray
    return width, height, bytes(out)


# ---------------------------------------------------------------------------
# Compact store: the bundle (ASCII + seed + params + hash)
# ---------------------------------------------------------------------------


@dataclass
class AsciiBundle:
    """Everything needed to regenerate or remix an image later."""

    version: int = BUNDLE_VERSION
    prompt: str = ""
    seed: int = 0
    style: str = ""
    src_width: int = 0
    src_height: int = 0
    src_sha256: str = ""
    charset: str = CHARSET_DENSE
    cols: int = 80
    rows: int = 0
    art: Tuple[str, ...] = ()
    params: Dict[str, Any] = field(default_factory=dict)

    def ascii_art(self) -> AsciiArt:
        return AsciiArt(
            cols=self.cols, rows=self.rows, charset=self.charset, lines=self.art
        )


def pack(bundle: AsciiBundle) -> str:
    """Serialize a bundle to its compact canonical text form."""
    doc = {
        "v": bundle.version,
        "prompt": bundle.prompt,
        "seed": bundle.seed,
        "style": bundle.style,
        "src": [bundle.src_width, bundle.src_height],
        "src_sha256": bundle.src_sha256,
        "charset": bundle.charset,
        "cols": bundle.cols,
        "rows": bundle.rows,
        "art": "\n".join(bundle.art),
        "params": bundle.params,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def unpack(text: str) -> AsciiBundle:
    """Parse and validate a packed bundle. Fails closed on anything off."""
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        raise BundleError(f"bundle is not valid JSON: {e}") from e
    if not isinstance(doc, dict):
        raise BundleError("bundle must be a JSON object")
    if doc.get("v") != BUNDLE_VERSION:
        raise BundleError(f"unsupported bundle version: {doc.get('v')!r}")
    try:
        art_lines = tuple(str(doc["art"]).split("\n"))
        cols, rows = int(doc["cols"]), int(doc["rows"])
        src_w, src_h = (int(x) for x in doc["src"])
        bundle = AsciiBundle(
            version=BUNDLE_VERSION,
            prompt=str(doc.get("prompt", "")),
            seed=int(doc.get("seed", 0)),
            style=str(doc.get("style", "")),
            src_width=src_w,
            src_height=src_h,
            src_sha256=str(doc.get("src_sha256", "")),
            charset=str(doc.get("charset", CHARSET_DENSE)),
            cols=cols,
            rows=rows,
            art=art_lines,
            params=dict(doc.get("params", {})),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise BundleError(f"bundle missing/invalid field: {e}") from e
    _validate_grid(bundle.cols, bundle.charset)
    # Triggers AsciiArt.__post_init__ dimension check:
    bundle.ascii_art()
    return bundle


def fingerprint(bundle: AsciiBundle) -> str:
    """Content hash of the canonical packed form."""
    return hashlib.sha256(pack(bundle).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Pipeline: compress / regenerate / remix
# ---------------------------------------------------------------------------


def compress_pixels(
    rgb: bytes,
    width: int,
    height: int,
    *,
    prompt: str = "",
    seed: int = 0,
    style: str = "",
    cols: int = 80,
    charset: str = CHARSET_DENSE,
    params: Optional[Dict[str, Any]] = None,
) -> AsciiBundle:
    """Compress a raw RGB buffer (the pre-PNG pixel hook) to a bundle."""
    from levi.media.local import encode_png as _encode_png  # local import: no cycle

    art = image_to_ascii(rgb, width, height, cols=cols, charset=charset)
    src_sha = hashlib.sha256(_encode_png(width, height, rgb)).hexdigest()
    return AsciiBundle(
        prompt=prompt,
        seed=seed,
        style=style,
        src_width=width,
        src_height=height,
        src_sha256=src_sha,
        charset=art.charset,
        cols=art.cols,
        rows=art.rows,
        art=art.lines,
        params=dict(params or {}),
    )


def compress_png(
    png: bytes,
    *,
    prompt: str = "",
    seed: int = 0,
    style: str = "",
    cols: int = 80,
    charset: str = CHARSET_DENSE,
    params: Optional[Dict[str, Any]] = None,
) -> AsciiBundle:
    """Compress PNG bytes: decode -> pixels -> ASCII bundle."""
    width, height, rgb = decode_png(png)
    bundle = compress_pixels(
        rgb, width, height, prompt=prompt, seed=seed, style=style,
        cols=cols, charset=charset, params=params,
    )
    # Record the hash of the actual input bytes (not our re-encode):
    bundle.src_sha256 = hashlib.sha256(bytes(png)).hexdigest()
    return bundle


def compress_file(
    path: str | Path,
    *,
    prompt: str = "",
    seed: int = 0,
    style: str = "",
    cols: int = 80,
    charset: str = CHARSET_DENSE,
    params: Optional[Dict[str, Any]] = None,
) -> AsciiBundle:
    """Compress a PNG file on disk to a bundle."""
    return compress_png(
        Path(path).read_bytes(), prompt=prompt, seed=seed, style=style,
        cols=cols, charset=charset, params=params,
    )


def regenerate(bundle: AsciiBundle, scale: int = 8) -> bytes:
    """Regenerate PNG bytes from a bundle. L1: byte-identical for same inputs."""
    from levi.media.local import encode_png as _encode_png

    width, height, rgb = ascii_to_rgb(bundle.ascii_art(), scale=scale)
    return _encode_png(width, height, rgb)


def regenerate_to(bundle: AsciiBundle, path: str | Path, scale: int = 8) -> str:
    """Regenerate a bundle to a PNG file. Returns the path as a string."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(regenerate(bundle, scale=scale))
    return str(dest)


def remix(
    bundle: AsciiBundle,
    *,
    charset: Optional[str] = None,
    invert: bool = False,
    cols: Optional[int] = None,
) -> AsciiBundle:
    """Remix a bundle: re-render its composition through a new charset or grid.

    Honest route: ASCII -> grayscale RGB -> re-encode. Deterministic.
    """
    new_charset = charset or bundle.charset
    if invert:
        new_charset = new_charset[::-1]
    _validate_grid(bundle.cols, new_charset)
    # Render at a high internal scale so re-gridding keeps detail.
    _, _, rgb = ascii_to_rgb(bundle.ascii_art(), scale=8)
    src_w, src_h = bundle.cols * 8, bundle.rows * 8
    art = image_to_ascii(rgb, src_w, src_h, cols=cols or bundle.cols, charset=new_charset)
    return AsciiBundle(
        version=BUNDLE_VERSION,
        prompt=bundle.prompt,
        seed=bundle.seed,
        style=bundle.style,
        src_width=bundle.src_width,
        src_height=bundle.src_height,
        src_sha256=bundle.src_sha256,
        charset=art.charset,
        cols=art.cols,
        rows=art.rows,
        art=art.lines,
        params={**bundle.params, "remixed_from": fingerprint(bundle)},
    )


def fidelity(
    rgb: bytes, width: int, height: int, art: AsciiArt
) -> Dict[str, float]:
    """Measure how faithfully ASCII art captures the source composition.

    Compares per-cell mean luminance of the source against the decoded gray
    level. Returns MAE (0-255), similarity (0-1), and PSNR (dB, inf if exact).
    """
    if len(rgb) != width * height * 3:
        raise ValueError("rgb buffer length does not match dimensions")
    n = len(art.charset)
    se, ae, count = 0.0, 0.0, 0
    for r, line in enumerate(art.lines):
        y0 = r * height // art.rows
        y1 = max(y0 + 1, (r + 1) * height // art.rows)
        for c, ch in enumerate(line):
            x0 = c * width // art.cols
            x1 = max(x0 + 1, (c + 1) * width // art.cols)
            total, n_px = 0.0, 0
            for y in range(y0, y1):
                base = y * width * 3
                for x in range(x0, x1):
                    o = base + x * 3
                    total += _luminance(rgb[o], rgb[o + 1], rgb[o + 2])
                    n_px += 1
            src_lum = total / n_px
            dec_gray = _char_level(ch, art.charset) * 255
            err = abs(src_lum - dec_gray)
            ae += err
            se += err * err
            count += 1
    mae = ae / count
    mse = se / count
    psnr = float("inf") if mse == 0 else 20 * math.log10(255 / math.sqrt(mse))
    return {"mae": mae, "similarity": 1.0 - mae / 255.0, "psnr_db": psnr}


# ---------------------------------------------------------------------------
# Thumbs-down selection loop
# ---------------------------------------------------------------------------

_DEFAULT_STYLES = ("abstract", "photo", "dark", "poster", "gradient")


@dataclass
class Candidate:
    """One picture on the table: real PNG on disk + its ASCII bundle."""

    id: str
    prompt: str
    seed: int
    style: str
    path: str
    bundle: AsciiBundle
    chosen: bool = False
    rejected: bool = False


class BrowseSession:
    """Cruise-and-pick loop: browse candidates, thumbs-down the misses,
    get a fresh set of alternatives of the desired picture to choose from.

    Deterministic: same master seed -> same candidate stream. L4: every
    thumbs_down() returns exactly per_round NEW candidates; rejected ids
    never reappear.
    """

    def __init__(
        self,
        prompt: str,
        *,
        styles: Optional[Sequence[str]] = None,
        per_round: int = 4,
        seed: Optional[int] = None,
        cols: int = 80,
        work_dir: Optional[str | Path] = None,
    ) -> None:
        if not prompt or not prompt.strip():
            raise CurateError("prompt must be a non-empty string")
        if not isinstance(per_round, int) or per_round < 1 or per_round > 16:
            raise CurateError("per_round must be an int in [1,16]")
        self.prompt = prompt.strip()
        self.styles = list(styles) if styles else list(_DEFAULT_STYLES)
        self.per_round = per_round
        self.master_seed = (
            seed if seed is not None
            else int.from_bytes(hashlib.sha256(prompt.encode()).digest()[:8], "big")
        )
        self.cols = cols
        _validate_grid(cols, CHARSET_DENSE)
        self.work_dir = Path(work_dir) if work_dir else Path(
            tempfile.mkdtemp(prefix="ascii-curate-")
        )
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._round = 0
        self._seen: Dict[str, Candidate] = {}
        self._rejected: set[str] = set()
        self._current: List[Candidate] = []
        self._final: Optional[Candidate] = None
        self._deal()

    def _candidate_seed(self, round_no: int, index: int) -> int:
        digest = hashlib.sha256(
            f"{self.master_seed}:{round_no}:{index}".encode()
        ).digest()
        return int.from_bytes(digest[:8], "big")

    def _deal(self) -> None:
        from levi.media import local as _local

        fresh: List[Candidate] = []
        for i in range(self.per_round):
            cseed = self._candidate_seed(self._round, i)
            style = self.styles[(self._round * self.per_round + i) % len(self.styles)]
            cid = f"r{self._round}c{i}"
            img = _local.generate(
                self.prompt, seed=cseed, style=style,
                save=True, save_dir=self.work_dir, width=256, height=256,
            )
            bundle = compress_file(
                img.path, prompt=self.prompt, seed=cseed, style=style,
                cols=self.cols, params={"session_round": self._round},
            )
            cand = Candidate(
                id=cid, prompt=self.prompt, seed=cseed, style=style,
                path=img.path, bundle=bundle,
            )
            self._seen[cid] = cand
            fresh.append(cand)
        self._round += 1
        self._current = fresh

    @property
    def candidates(self) -> List[Candidate]:
        return list(self._current)

    @property
    def final(self) -> Optional[Candidate]:
        return self._final

    def thumbs_down(self, image_id: str) -> List[Candidate]:
        """Reject a picture; get a fresh alternative set to pick from."""
        cand = self._seen.get(image_id)
        if cand is None:
            raise CurateError(f"unknown candidate id: {image_id!r}")
        if cand.rejected:
            raise CurateError(f"candidate {image_id!r} already rejected")
        if self._final is not None:
            raise CurateError("session already has a final pick")
        cand.rejected = True
        self._rejected.add(image_id)
        self._deal()
        return self.candidates

    def thumbs_up(self, image_id: str) -> Candidate:
        """Lock in the chosen picture."""
        cand = self._seen.get(image_id)
        if cand is None:
            raise CurateError(f"unknown candidate id: {image_id!r}")
        if cand.rejected:
            raise CurateError(f"candidate {image_id!r} was rejected")
        cand.chosen = True
        self._final = cand
        return cand

    pick = thumbs_up  # alias: picking IS the thumbs-up

    def export_bundle(self, image_id: str) -> str:
        """Packed ASCII bundle for storage; the PNG can be regenerated later."""
        cand = self._seen.get(image_id)
        if cand is None:
            raise CurateError(f"unknown candidate id: {image_id!r}")
        return pack(cand.bundle)

    def history(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "rounds_dealt": self._round,
            "seen": len(self._seen),
            "rejected": sorted(self._rejected),
            "final": self._final.id if self._final else None,
        }


# ---------------------------------------------------------------------------
# Academy M-track drill runner (register-ready; do NOT edit session_exercises.py
# to wire it — add one line to EXERCISE_RUNNERS there:
#     "media-ascii": ex_media_ascii,)
# ---------------------------------------------------------------------------


def ex_media_ascii(entry, lesson, research, work_dir=None):
    """Drill: round-trip a real image through ASCII compression.

    Generates a procedural PNG, compresses it to a bundle, regenerates it,
    and proves L1 (byte-identical re-regeneration) and L2 (bundle < PNG).
    """
    from levi.media import local as _local

    wd = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="media-ascii-"))
    wd.mkdir(parents=True, exist_ok=True)
    title = str(entry.get("title", "ascii drill"))
    dseed = int.from_bytes(hashlib.sha256(title.encode()).digest()[:8], "big")

    checks: List[Dict[str, Any]] = []

    img = _local.generate(
        f"academy ascii drill: {title}", seed=dseed, style="dark",
        save=True, save_dir=wd, width=256, height=256, caption_band="bottom",
    )
    png_bytes = Path(img.path).read_bytes()
    checks.append({"name": "source PNG generated", "passed": _png_ok(Path(img.path))})

    bundle = compress_file(img.path, prompt=img.prompt, seed=img.seed, style=img.style)
    packed = pack(bundle)
    checks.append({
        "name": "bundle smaller than PNG (L2)",
        "passed": len(packed.encode("utf-8")) < len(png_bytes),
        "detail": f"{len(packed.encode('utf-8'))}B < {len(png_bytes)}B",
    })

    regen_a = regenerate(bundle, scale=4)
    regen_b = regenerate(bundle, scale=4)
    checks.append({
        "name": "re-regeneration byte-identical (L1)",
        "passed": regen_a == regen_b and len(regen_a) > 0,
    })
    regen_path = wd / "regenerated.png"
    regen_path.write_bytes(regen_a)
    checks.append({"name": "regenerated PNG written", "passed": _png_ok(regen_path)})

    # Decode the source PNG to pixels for the fidelity measure.
    _, _, src_rgb = decode_png(png_bytes)
    fid = fidelity(src_rgb, img.width, img.height, bundle.ascii_art())
    checks.append({
        "name": "fidelity measured",
        "passed": 0.0 < fid["similarity"] <= 1.0,
        "detail": f"similarity={fid['similarity']:.3f} mae={fid['mae']:.1f}",
    })

    bundle_path = wd / "bundle.txt"
    bundle_path.write_text(packed, encoding="utf-8")

    passed = sum(1 for c in checks if c["passed"])
    return {
        "artifact": {
            "status": "ok",
            "op": "ascii-roundtrip",
            "source_png": str(img.path),
            "bundle_txt": str(bundle_path),
            "regenerated_png": str(regen_path),
            "bundle_bytes": len(packed.encode("utf-8")),
            "png_bytes": len(png_bytes),
            "ratio": round(len(png_bytes) / len(packed.encode("utf-8")), 2),
            "fidelity": {k: round(v, 4) if isinstance(v, float) else v for k, v in fid.items()},
            "bundle_fingerprint": fingerprint(bundle),
        },
        "score": round(passed / len(checks), 3),
        "checks": checks,
        "notes": f"{passed}/{len(checks)} rubric checks passed. "
                 "Real artifacts: source PNG, ASCII bundle, regenerated PNG.",
    }


def _png_ok(path: Path) -> bool:
    try:
        return path.stat().st_size > 0 and path.read_bytes()[:8] == _PNG_SIG
    except OSError:
        return False
