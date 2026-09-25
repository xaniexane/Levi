"""Mode-shifted 5-bit text code, ITA2 (Baudot) shaped.

Studied from: protocols-hunt-20260916-0041/report.md [Find 3 - Telex]

Functional description: thirty-two 5-bit codes carry sixty-two symbols by
switching between two shift states. Each code is interpreted in the
current state — LTRS (letters) or FIGS (figures) — and the two dedicated
shift codes LTRS (11111) and FIGS (11011) flip the state for everything
that follows. ``encode`` walks the input, inserting shift codes whenever
the next character lives in the other state; ``decode`` walks a code
stream, tracking state, and raises on unknown codes. Both directions are
pure functions of the two code tables plus the shift state machine.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: the classic ITA2 code tables (letters A–Z, figures 0–9 and
punctuation); bell is carried as the control character ``\\x07``;
national figure variants are not covered.
"""

from __future__ import annotations

from typing import Dict, List

ORIGIN = "levi-revival/mode-shift-code"

LTRS = 0b11111  # letters shift
FIGS = 0b11011  # figures shift
BLANK = 0b00000
SPACE = 0b00100
CR = 0b00010
LF = 0b01000

# 5-bit code -> (letters symbol, figures symbol)
_CODE_TABLE: Dict[int, tuple] = {
    0b00011: ("A", "-"),
    0b11001: ("B", "?"),
    0b01110: ("C", ":"),
    0b01001: ("D", "$"),
    0b00001: ("E", "3"),
    0b01101: ("F", "!"),
    0b11010: ("G", "&"),
    0b10100: ("H", "#"),
    0b00110: ("I", "8"),
    0b01011: ("J", "\x07"),  # bell
    0b01111: ("K", "("),
    0b10010: ("L", ")"),
    0b11100: ("M", "."),
    0b01100: ("N", ","),
    0b11000: ("O", "9"),
    0b10110: ("P", "0"),
    0b10111: ("Q", "1"),
    0b00101: ("R", "4"),
    0b01010: ("S", "'"),
    0b10000: ("T", "5"),
    0b00111: ("U", "7"),
    0b11110: ("V", "="),
    0b10011: ("W", "2"),
    0b11101: ("X", "/"),
    0b10101: ("Y", "6"),
    0b10001: ("Z", "+"),
    SPACE: (" ", " "),
    CR: ("\r", "\r"),
    LF: ("\n", "\n"),
    BLANK: ("", ""),
}

_LETTER_CODES: Dict[str, int] = {}
_FIGURE_CODES: Dict[str, int] = {}
for _code, (_ltr, _fig) in _CODE_TABLE.items():
    if _ltr:
        _LETTER_CODES.setdefault(_ltr, _code)
    if _fig and _fig != _ltr:
        _FIGURE_CODES.setdefault(_fig, _code)


class ModeShiftError(ValueError):
    """Raised for unencodable characters or bad code streams."""


class ShiftState:
    """Tracks which shift the code stream is currently in."""

    LETTERS = "letters"
    FIGURES = "figures"

    def __init__(self) -> None:
        self.state = self.LETTERS

    def to_letters(self) -> List[int]:
        if self.state == self.LETTERS:
            return []
        self.state = self.LETTERS
        return [LTRS]

    def to_figures(self) -> List[int]:
        if self.state == self.FIGURES:
            return []
        self.state = self.FIGURES
        return [FIGS]


def encode(text: str) -> List[int]:
    """Encode text to 5-bit codes, inserting shift codes as needed.

    Starts in letters shift. Case is folded to upper.
    """
    codes: List[int] = []
    shifter = ShiftState()
    for ch in text.upper():
        if ch in _LETTER_CODES:
            codes.extend(shifter.to_letters())
            codes.append(_LETTER_CODES[ch])
        elif ch in _FIGURE_CODES:
            codes.extend(shifter.to_figures())
            codes.append(_FIGURE_CODES[ch])
        else:
            raise ModeShiftError(f"character {ch!r} has no ITA2 code")
    return codes


def decode(codes: List[int]) -> str:
    """Decode 5-bit codes back to text, tracking the shift state."""
    out: List[str] = []
    state = ShiftState.LETTERS
    for code in codes:
        if code == LTRS:
            state = ShiftState.LETTERS
            continue
        if code == FIGS:
            state = ShiftState.FIGURES
            continue
        if code not in _CODE_TABLE:
            raise ModeShiftError(f"unknown 5-bit code {code:05b}")
        letter, figure = _CODE_TABLE[code]
        out.append(letter if state == ShiftState.LETTERS else figure)
    return "".join(out)


def pack(codes: List[int]) -> bytes:
    """Pack 5-bit codes into bytes (MSB-first bit stream)."""
    acc = 0
    bits = 0
    out = bytearray()
    for code in codes:
        acc = (acc << 5) | (code & 0x1F)
        bits += 5
        while bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    if bits:
        out.append((acc << (8 - bits)) & 0xFF)
    return bytes(out)


def unpack(data: bytes, count: int) -> List[int]:
    """Unpack the first ``count`` 5-bit codes from a packed byte stream."""
    codes: List[int] = []
    acc = 0
    bits = 0
    for byte in data:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5 and len(codes) < count:
            bits -= 5
            codes.append((acc >> bits) & 0x1F)
    if len(codes) < count:
        raise ModeShiftError("packed data holds fewer codes than requested")
    return codes
