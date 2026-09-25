"""Vendored QR encoder — stdlib only, no dependencies, no network.

Why vendored: the phone (Termux) runs Void Box payments with zero pip
installs, so the QR encoder must work on stdlib alone. PIL is used for
PNG only when importable; SVG and ASCII renderers are pure stdlib.

Scope (declared honestly): byte mode, versions 1-4, EC levels L/M/Q/H.
Payment deep links and invite URIs are short (< 100 bytes), so version 4
(62 bytes at EC-M) covers every payload this package builds. Longer
input raises :class:`QRCapacityError` naming the limit — never silently
truncated, never faked.

Correctness (how we know it scans):
- Reed-Solomon EC bytes are verified by the zero-remainder check — the
  same division a decoder performs.
- Format information carries its BCH error-correction bits and is
  decoded back in tests.
- Data placement is round-tripped (place -> read back -> compare).
- Cross-checked against the independent ``segno`` encoder
  (test-time only; segno is NOT a runtime dependency). The cross-check
  caught and fixed three real bugs: format info drawn after data
  placement (corrupted data modules), format bit order inverted
  (spec is MSB-first), and format copy-2 swallowing the fixed dark
  module. After the fixes: format info bit-identical to segno, mask
  formulas identical to the ISO 18004 table segno's source cites, and
  data-region codewords identical for every case where segno uses a
  single byte-mode segment. Remaining matrix differences are segno's
  own choices (optimized multi-mode segmentation, a 0x00 pad-byte
  quirk at one byte boundary, different mask pick) — all valid, none
  copied.

Scope (declared honestly): byte mode, versions 1-4, EC levels L/M/Q/H.

LAWS:
- Q1 — Byte mode, versions 1-4, EC L/M/Q/H only. Anything else is
  refused, never approximated.
- Q2 — No silent truncation: input longer than the selected version's
  capacity raises QRCapacityError.
- Q3 — EC bytes must satisfy the zero-remainder check before a matrix
  is returned (checked at encode time, cheap).
- Q4 — Mask chosen by the real penalty rules (all 8 evaluated), never
  hardcoded.
- Q5 — Renderers never invent data: ASCII/SVG/PNG all draw the same
  validated matrix.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

#: Declared laws, machine-readable.
LAWS = (
    ("Q1", "Byte mode, versions 1-4, EC L/M/Q/H only; anything else refused, never approximated."),
    ("Q2", "No silent truncation: over-capacity input raises QRCapacityError."),
    ("Q3", "EC bytes must satisfy the zero-remainder check before a matrix is returned."),
    ("Q4", "Mask chosen by the real penalty rules (all 8 evaluated), never hardcoded."),
    ("Q5", "Renderers never invent data: ASCII/SVG/PNG all draw the same validated matrix."),
)

_EC_LEVELS = ("L", "M", "Q", "H")
_EC_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}

# version -> ec_level -> (ec_codewords_per_block, [(n_blocks, data_codewords), ...])
_BLOCKS = {
    1: {
        "L": (7, [(1, 19)]),
        "M": (10, [(1, 16)]),
        "Q": (13, [(1, 13)]),
        "H": (17, [(1, 9)]),
    },
    2: {
        "L": (10, [(1, 34)]),
        "M": (16, [(1, 28)]),
        "Q": (22, [(1, 22)]),
        "H": (28, [(1, 16)]),
    },
    3: {
        "L": (15, [(1, 55)]),
        "M": (26, [(1, 44)]),
        "Q": (18, [(2, 17)]),
        "H": (22, [(2, 13)]),
    },
    4: {
        "L": (20, [(1, 80)]),
        "M": (18, [(2, 32)]),
        "Q": (26, [(2, 24)]),
        "H": (16, [(4, 9)]),
    },
}

_ALIGNMENT_CENTERS = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26]}
_REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7}
_FORMAT_MASK_XOR = 0b101010000010010


class QRError(ValueError):
    """Base QR encoder failure."""


class QRCapacityError(QRError):
    """Payload exceeds version 4 capacity — shorten it or split it."""


class QRRenderError(QRError):
    """A renderer could not run (e.g. PIL missing for PNG)."""


# ---------------------------------------------------------------------------
# GF(256) arithmetic (primitive polynomial x^8+x^4+x^3+x^2+1 = 0x11D)
# ---------------------------------------------------------------------------


def _build_gf() -> Tuple[List[int], List[int]]:
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_GF_EXP, _GF_LOG = _build_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] + _GF_LOG[b]) % 255]


def _rs_generator(degree: int) -> List[int]:
    """Generator polynomial of given degree, coefficients high-first."""
    gen = [1]
    for i in range(degree):
        nxt = [0] * (len(gen) + 1)
        ai = _GF_EXP[i]
        for j, coef in enumerate(gen):
            nxt[j] ^= _gf_mul(coef, ai)  # * (x + a^i): constant term
            nxt[j + 1] ^= coef           # x term
        gen = nxt
    return gen


def _rs_compute_ec(data: bytes, ec_count: int) -> bytes:
    """Reed-Solomon error-correction codewords for one block."""
    gen = _rs_generator(ec_count)
    msg = bytearray(data) + bytearray(ec_count)
    for i in range(len(data)):
        coef = msg[i]
        if coef:
            for j in range(1, len(gen)):
                g = gen[j]
                if g:
                    msg[i + j] ^= _gf_mul(g, coef)
    return bytes(msg[len(data):])


def rs_remainder_is_zero(codewords: Sequence[int], ec_count: int) -> bool:
    """Independent check: data+EC codewords divided by the generator
    polynomial must leave a zero remainder. This is the same division a
    decoder performs — it validates the EC bytes, not just the data."""
    gen = _rs_generator(ec_count)
    msg = bytearray(codewords) + bytearray(ec_count)
    # Synthetic division over the full received sequence.
    for i in range(len(codewords)):
        coef = msg[i]
        if coef:
            for j in range(1, len(gen)):
                g = gen[j]
                if g:
                    msg[i + j] ^= _gf_mul(g, coef)
    return all(b == 0 for b in msg[len(codewords):])


# ---------------------------------------------------------------------------
# Bit stream: byte-mode data encoding
# ---------------------------------------------------------------------------


def _byte_capacity(version: int, ec_level: str) -> int:
    """Max payload bytes: (data_codewords*8 - 12 mode/count bits) // 8."""
    _, groups = _BLOCKS[version][ec_level]
    total_data = sum(n * d for n, d in groups)
    return (total_data * 8 - 12) // 8


def _pick_version(data_len: int, ec_level: str) -> int:
    for version in (1, 2, 3, 4):
        if data_len <= _byte_capacity(version, ec_level):
            return version
    raise QRCapacityError(
        "payload is %d bytes; the largest supported code (version 4, "
        "EC %s) holds %d. Shorten the payload — it is never truncated."
        % (data_len, ec_level, _byte_capacity(4, ec_level))
    )


def _encode_data_codewords(data: bytes, version: int, ec_level: str) -> List[bytes]:
    """Byte-mode bit stream -> per-block data codeword lists."""
    _, groups = _BLOCKS[version][ec_level]
    total_data = sum(n * d for n, d in groups)
    bits: List[int] = []
    bits += [0, 1, 0, 0]  # byte mode indicator
    n = len(data)
    for i in range(7, -1, -1):
        bits.append((n >> i) & 1)  # 8-bit character count (versions 1-9)
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    capacity_bits = total_data * 8
    terminator = min(4, capacity_bits - len(bits))
    bits += [0] * terminator
    while len(bits) % 8:
        bits.append(0)
    codewords = bytearray()
    for i in range(0, len(bits), 8):
        value = 0
        for b in bits[i:i + 8]:
            value = (value << 1) | b
        codewords.append(value)
    pad = [0xEC, 0x11]
    pi = 0
    while len(codewords) < total_data:
        codewords.append(pad[pi % 2])
        pi += 1
    # Split into blocks.
    blocks: List[bytes] = []
    off = 0
    for n_blocks, dcount in groups:
        for _ in range(n_blocks):
            blocks.append(bytes(codewords[off:off + dcount]))
            off += dcount
    return blocks


def _interleave(blocks: List[bytes], ec_per_block: int) -> Tuple[List[int], List[bytes]]:
    """Interleave data codewords, then EC codewords, across blocks.

    Returns (interleaved_codewords, per_block_ec) so callers can verify
    each block's EC bytes independently (Q3)."""
    ec_blocks = [_rs_compute_ec(b, ec_per_block) for b in blocks]
    out: List[int] = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_per_block):
        for e in ec_blocks:
            out.append(e[i])
    return out, ec_blocks


# ---------------------------------------------------------------------------
# Matrix: function patterns, format info, data placement, masking
# ---------------------------------------------------------------------------


def _blank_matrix(version: int) -> Tuple[List[List[int]], List[List[bool]]]:
    n = 4 * version + 17
    return [[0] * n for _ in range(n)], [[False] * n for _ in range(n)]


def _draw_finder(matrix, func, r: int, c: int) -> None:
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(matrix) and 0 <= cc < len(matrix):
                in_pat = 0 <= dr <= 6 and 0 <= dc <= 6
                dark = in_pat and (
                    dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)
                )
                matrix[rr][cc] = 1 if dark else 0
                func[rr][cc] = True


def _draw_function_patterns(matrix, func, version: int) -> None:
    n = len(matrix)
    _draw_finder(matrix, func, 0, 0)
    _draw_finder(matrix, func, 0, n - 7)
    _draw_finder(matrix, func, n - 7, 0)
    # Timing patterns (row 6 / column 6, between the separators).
    for i in range(8, n - 8):
        v = 1 if i % 2 == 0 else 0
        matrix[6][i] = v
        func[6][i] = True
        matrix[i][6] = v
        func[i][6] = True
    # Alignment patterns (versions 2+).
    centers = _ALIGNMENT_CENTERS[version]
    for cy in centers:
        for cx in centers:
            if (cy <= 8 and cx <= 8) or (cy <= 8 and cx >= n - 9) or (cy >= n - 9 and cx <= 8):
                continue  # would overlap a finder
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    dark = max(abs(dr), abs(dc)) != 1
                    matrix[cy + dr][cx + dc] = 1 if dark else 0
                    func[cy + dr][cx + dc] = True
    # Dark module.
    matrix[4 * version + 9][8] = 1
    func[4 * version + 9][8] = True


def _format_positions(version: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Format-info coordinates in MSB-first bit order (bit 14 first).

    Copy 1 wraps the top-left finder; copy 2 splits into a 7-module
    vertical strip (bits 14..8) and an 8-module horizontal strip
    (bits 7..0). The dark module at (n-8, 8) is NOT a format module —
    it sits just above the vertical strip and stays dark."""
    n = 4 * version + 17
    copy1: List[Tuple[int, int]] = (
        [(8, i) for i in range(6)]
        + [(8, 7), (8, 8), (7, 8)]
        + [(5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    )
    copy2: List[Tuple[int, int]] = (
        [(n - 1 - i, 8) for i in range(7)]      # bits 14..8
        + [(8, n - 8 + j) for j in range(8)]    # bits 7..0
    )
    return copy1, copy2


def _reserve_format(func: List[List[bool]], version: int) -> None:
    """Mark format-info positions as function modules BEFORE data
    placement. The bits are drawn later (they depend on the chosen
    mask), but the positions must be reserved up front — otherwise data
    bits land in the format region and are destroyed when the format
    bits are drawn over them."""
    copy1, copy2 = _format_positions(version)
    for r, c in copy1 + copy2:
        func[r][c] = True


def _format_bits(ec_level: str, mask: int) -> int:
    """15-bit format value: 5 data bits + 10 BCH bits, XOR-masked."""
    data = (_EC_BITS[ec_level] << 3) | mask
    # BCH(15,5): divide data<<10 by generator 0x537, take 10-bit remainder.
    rem = data << 10
    gen = 0x537
    while rem.bit_length() > 10:
        rem ^= gen << (rem.bit_length() - 11)
    return ((data << 10) | rem) ^ _FORMAT_MASK_XOR


def _draw_format(matrix, func, version: int, ec_level: str, mask: int) -> None:
    """Draw the 15 format bits into both reserved copies, MSB first."""
    bits = _format_bits(ec_level, mask)
    b = [(bits >> i) & 1 for i in range(14, -1, -1)]  # b[0] = MSB (bit 14)
    copy1, copy2 = _format_positions(version)
    for (r, c), bit in zip(copy1 + copy2, b + b):
        matrix[r][c] = bit
        func[r][c] = True


def _place_data(matrix, func, codewords: Sequence[int]) -> None:
    """Zigzag data placement, bottom-right upward, skipping column 6 and
    every function module. Remainder bits (always 0) fill the tail."""
    n = len(matrix)
    bits: List[int] = []
    for cw in codewords:
        for i in range(7, -1, -1):
            bits.append((cw >> i) & 1)
    bi = 0
    upward = True
    for col in range(n - 1, 0, -2):
        if col <= 6:
            col -= 1  # skip the vertical timing column; pairs below it
        # shift left: (5,4), (3,2), (1,0) — every column visited once
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if func[r][c]:
                    continue
                matrix[r][c] = bits[bi] if bi < len(bits) else 0
                bi += 1
        upward = not upward


def _read_data_bits(matrix, func) -> List[int]:
    """Inverse of _place_data: read data-module bits in zigzag order.
    Used by tests to prove placement round-trips."""
    n = len(matrix)
    bits: List[int] = []
    upward = True
    for col in range(n - 1, 0, -2):
        if col <= 6:
            col -= 1  # skip the vertical timing column (mirrors _place_data)
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if func[r][c]:
                    continue
                bits.append(matrix[r][c])
        upward = not upward
    return bits


_MASK_FNS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
)


def _apply_mask(matrix, func, mask: int) -> None:
    fn = _MASK_FNS[mask]
    n = len(matrix)
    for r in range(n):
        for c in range(n):
            if not func[r][c] and fn(r, c):
                matrix[r][c] ^= 1


def _penalty(matrix) -> int:
    n = len(matrix)
    score = 0
    # Rule 1: runs of 5+ in rows/columns.
    for line in (matrix, [list(col) for col in zip(*matrix)]):
        for row in line:
            run = 1
            for i in range(1, len(row)):
                if row[i] == row[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run = 1
            if run >= 5:
                score += 3 + (run - 5)
    # Rule 2: 2x2 blocks.
    for r in range(n - 1):
        for c in range(n - 1):
            v = matrix[r][c]
            if matrix[r][c + 1] == v == matrix[r + 1][c] == matrix[r + 1][c + 1]:
                score += 3
    # Rule 3: finder-like patterns.
    pat1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pat2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for line in (matrix, [list(col) for col in zip(*matrix)]):
        for row in line:
            for i in range(len(row) - 10):
                seg = row[i:i + 11]
                if seg == pat1 or seg == pat2:
                    score += 40
    # Rule 4: dark-module ratio.
    dark = sum(sum(row) for row in matrix)
    total = n * n
    ratio = dark * 100 / total
    prev = int(ratio // 5) * 5
    nxt = prev + 5
    score += min(abs(prev - 50), abs(nxt - 50)) // 5 * 10
    return score


def _choose_mask(matrix, func) -> int:
    best, best_score = 0, None
    for mask in range(8):
        trial = [row[:] for row in matrix]
        _apply_mask(trial, func, mask)
        s = _penalty(trial)
        if best_score is None or s < best_score:
            best, best_score = mask, s
    return best


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QRCode:
    """One encoded QR symbol. ``matrix`` is rows of 0/1, 1 = dark."""

    def __init__(self, text: str, ec_level: str = "M"):
        if ec_level not in _EC_LEVELS:
            raise QRError(
                "ec_level must be one of %s, got %r." % (_EC_LEVELS, ec_level)
            )
        if not isinstance(text, str) or not text:
            raise QRError("QR payload must be non-empty text.")
        data = text.encode("utf-8")
        version = _pick_version(len(data), ec_level)
        self.version = version
        self.ec_level = ec_level
        self.size = 4 * version + 17

        ec_per_block, _ = _BLOCKS[version][ec_level]
        blocks = _encode_data_codewords(data, version, ec_level)
        codewords, ec_blocks = _interleave(blocks, ec_per_block)

        # Q3: the zero-remainder check runs at encode time — a matrix is
        # never returned with unverified EC bytes.
        for b, eb in zip(blocks, ec_blocks):
            if not rs_remainder_is_zero(list(b) + list(eb), ec_per_block):
                raise QRError(
                    "internal: RS zero-remainder check failed — refusing "
                    "to emit an unverified matrix."
                )

        matrix, func = _blank_matrix(version)
        _draw_function_patterns(matrix, func, version)
        _reserve_format(func, version)  # format positions are function
        # modules BEFORE data placement — the bits are drawn after the
        # mask is chosen, but the positions must be reserved now.
        _place_data(matrix, func, codewords)
        mask = _choose_mask(matrix, func)
        _apply_mask(matrix, func, mask)
        _draw_format(matrix, func, version, ec_level, mask)
        self.mask = mask
        self.matrix = matrix

    # -- renderers (Q5: all draw the same validated matrix) ---------------

    def to_ascii(self, *, border: int = 2) -> str:
        """Terminal rendering. border = quiet-zone modules."""
        n = self.size
        blank = "  " * (n + 2 * border)
        q = "  " * border
        dark, light = "\u2588\u2588", "  "
        lines = [blank] * border
        for row in self.matrix:
            lines.append(q + "".join(dark if v else light for v in row) + q)
        lines += [blank] * border
        return "\n".join(lines)

    def to_svg(self, *, scale: int = 8, border: int = 4) -> str:
        """Standalone SVG. Pure stdlib."""
        n = self.size
        dim = (n + 2 * border) * scale
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">' % (dim, dim, dim, dim),
            '<rect width="%d" height="%d" fill="white"/>' % (dim, dim),
            '<g fill="black">',
        ]
        for r, row in enumerate(self.matrix):
            for c, v in enumerate(row):
                if v:
                    x = (c + border) * scale
                    y = (r + border) * scale
                    parts.append(
                        '<rect x="%d" y="%d" width="%d" height="%d"/>'
                        % (x, y, scale, scale)
                    )
        parts.append("</g></svg>")
        return "\n".join(parts)

    def to_png(self, *, scale: int = 8, border: int = 4) -> bytes:
        """PNG bytes via PIL. Raises QRRenderError when PIL is missing —
        the remedy names the install, never a fake image."""
        try:
            from PIL import Image
        except ImportError:
            raise QRRenderError(
                "PNG rendering needs PIL (Pillow): `pip install pillow`. "
                "SVG and ASCII renderers need nothing."
            )
        n = self.size
        dim = n + 2 * border
        img = Image.new("1", (dim, dim), 1)
        px = img.load()
        for r, row in enumerate(self.matrix):
            for c, v in enumerate(row):
                px[c + border, r + border] = 0 if v else 1
        if scale != 1:
            img = img.resize((dim * scale, dim * scale), Image.NEAREST)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def encode_qr(text: str, ec_level: str = "M") -> QRCode:
    """Encode *text* (UTF-8, byte mode) into a validated QR symbol."""
    return QRCode(text, ec_level)


# ---------------------------------------------------------------------------
# Payload builders — the QR texts this package actually encodes
# ---------------------------------------------------------------------------


def payment_qr_text(plugin_name: str, deep_link: str) -> str:
    """The QR payload for a payment request: the plugin's deep link,
    verbatim. Scanners open it in the payment app."""
    if not deep_link or not isinstance(deep_link, str):
        raise QRError("payment QR needs a non-empty deep link.")
    return deep_link


def invite_qr_text(room_id: str, relay_host: str, relay_port: int) -> str:
    """Share QR for a room invite. Parsed by the Messenger client."""
    if not room_id or not relay_host:
        raise QRError("invite QR needs a room id and relay host.")
    return "voidbox://invite?room=%s&relay=%s:%d" % (room_id, relay_host, int(relay_port))


def profile_qr_text(kind: str, ref_id: str) -> str:
    """Share QR for a creator profile / listing. *kind* is one of
    creator, listing, channel."""
    if kind not in ("creator", "listing", "channel"):
        raise QRError("profile QR kind must be creator, listing, or channel.")
    if not ref_id:
        raise QRError("profile QR needs a reference id.")
    return "voidbox://%s/%s" % (kind, ref_id)


def payment_qr(plugin_name: str, deep_link: str, ec_level: str = "M") -> QRCode:
    """QR symbol for a payment request: encodes the plugin's deep link."""
    return QRCode(payment_qr_text(plugin_name, deep_link), ec_level)


def invite_qr(room_id: str, relay_host: str, relay_port: int,
              ec_level: str = "M") -> QRCode:
    """QR symbol for a room invite."""
    return QRCode(invite_qr_text(room_id, relay_host, relay_port), ec_level)


def profile_qr(kind: str, ref_id: str, ec_level: str = "M") -> QRCode:
    """QR symbol for a creator profile / listing / channel share."""
    return QRCode(profile_qr_text(kind, ref_id), ec_level)


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked QR invariants."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    # Q1: bad EC level refused; empty payload refused.
    for bad in ("X", ""):
        try:
            QRCode("hi", bad)
            check("Q1", False, "bad ec_level %r accepted" % (bad,))
        except QRError:
            check("Q1", True, "bad ec_level %r refused" % (bad,))
    try:
        QRCode("hi", None)  # type: ignore[arg-type]
        check("Q1", False, "ec_level None accepted")
    except QRError:
        check("Q1", True, "ec_level None refused")
    try:
        QRCode("")
        check("Q1", False, "empty payload accepted")
    except QRError:
        check("Q1", True, "empty payload refused")
    # Q2: over-capacity refused, never truncated.
    try:
        QRCode("x" * 500, "M")
        check("Q2", False, "500-byte payload accepted")
    except QRCapacityError:
        check("Q2", True, "500-byte payload refused with QRCapacityError")
    # Q3 spot-check: a fresh encode carries a verified matrix.
    qr = QRCode("voidbox", "M")
    n = qr.size
    dark = sum(sum(row) for row in qr.matrix)
    check("Q3", 0 < dark < n * n, "matrix %dx%d has %d dark modules" % (n, n, dark))
    # Finder patterns present at three corners.
    def _finder_ok(r0: int, c0: int) -> bool:
        for dr in range(7):
            for dc in range(7):
                want = dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)
                if bool(qr.matrix[r0 + dr][c0 + dc]) != want:
                    return False
        return True
    check(
        "Q1",
        _finder_ok(0, 0) and _finder_ok(0, n - 7) and _finder_ok(n - 7, 0),
        "finder patterns at three corners",
    )
    # Q5: renderers agree on dimensions.
    svg = qr.to_svg(scale=4, border=2)
    want_dim = (qr.size + 2 * 2) * 4
    check("Q5", 'width="%d"' % want_dim in svg, "svg dimensions match matrix")
    return results
