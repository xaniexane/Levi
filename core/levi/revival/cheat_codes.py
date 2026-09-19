"""Cheat codes as user-controlled difficulty dials: compare-and-replace patches.

Studied from: dead-game-genres-2026-09-16/report.md [Entries - Game Genie
and Cheat Codes] (the device's shape: a pass-through cartridge intercepting
memory reads, comparing the value on the address bus and replacing it when
it matches - codes as user-controlled difficulty dials, applied live without
modifying the cartridge).

This is an original, from-scratch implementation for LEVI. A ``MemoryBus``
simulates flat byte-addressable memory. A ``PatchCode`` is a triple
``(address, compare, replace)``: when a read hits ``address`` and the stored
byte equals ``compare``, the bus returns ``replace`` instead - the game logic
never knows. Codes encode to short 9-letter strings using an original
16-letter alphabet plus a checksum nibble, so mistyped codes are rejected
instead of silently misbehaving. A ``CheatCartridge`` holds the active code
set, applies it on every read, and logs which codes fired. Named ``Dial``
presets bundle codes into plain-language difficulty settings.

Codes never write to memory - they only substitute values on read, matching
the studied pass-through behavior.

Honest limits: this is a teaching simulation, not an emulator - no CPU, no
ROM image, no timing; addresses are flat (no banking or mirroring).

Public surface:
- ``MemoryBus(size)``: ``poke(addr, value)`` (direct write), ``raw_read(addr)``.
- ``PatchCode(address, compare, replace)``: ``encode()`` / ``PatchCode.decode(s)``.
- ``CheatCartridge(bus)``: ``add`` / ``remove`` / ``read`` (patched) / ``apply_dial`` /
  ``clear``; ``fired`` log.
- ``DIALS``: preset difficulty dials; ``list_dials()``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/cheat-codes"

# Original 16-letter alphabet (LEVI's own design, not the historical one).
_ALPHABET = "BCDFGHJKLMNPQRST"
_ALPHA_INDEX = {ch: i for i, ch in enumerate(_ALPHABET)}

_CODE_LEN = 9


def _nibbles_to_code(nibbles: List[int]) -> str:
    return "".join(_ALPHABET[n & 0xF] for n in nibbles)


def _code_to_nibbles(code: str) -> List[int]:
    code = code.strip().upper().replace("-", "").replace(" ", "")
    if len(code) != _CODE_LEN or any(ch not in _ALPHA_INDEX for ch in code):
        raise ValueError(
            f"bad code {code!r}: need {_CODE_LEN} letters from {_ALPHABET}"
        )
    return [_ALPHA_INDEX[ch] for ch in code]


@dataclass(frozen=True)
class PatchCode:
    """One compare-and-replace patch: if mem[address] == compare, reads return replace.

    Encoding packs 8 nibbles (address x4, compare x2, replace x2) plus a
    checksum nibble, so any single-letter typo fails the checksum instead of
    patching wrongly.
    """

    address: int
    compare: int
    replace: int

    def __post_init__(self) -> None:
        if not (0 <= self.address <= 0xFFFF):
            raise ValueError("address must fit in 16 bits")
        for name, v in (("compare", self.compare), ("replace", self.replace)):
            if not (0 <= v <= 0xFF):
                raise ValueError(f"{name} must be a byte")

    def encode(self) -> str:
        nibbles = [
            (self.address >> 12) & 0xF,
            (self.address >> 8) & 0xF,
            (self.address >> 4) & 0xF,
            self.address & 0xF,
            (self.compare >> 4) & 0xF,
            self.compare & 0xF,
            (self.replace >> 4) & 0xF,
            self.replace & 0xF,
        ]
        checksum = 0
        for n in nibbles:
            checksum ^= n
        nibbles.append(checksum)
        return _nibbles_to_code(nibbles)

    @classmethod
    def decode(cls, code: str) -> "PatchCode":
        nibbles = _code_to_nibbles(code)
        checksum = 0
        for n in nibbles[:8]:
            checksum ^= n
        if nibbles[8] != checksum:
            raise ValueError(f"bad code {code.strip()!r}: checksum mismatch (typo?)")
        return cls(
            address=(nibbles[0] << 12)
            | (nibbles[1] << 8)
            | (nibbles[2] << 4)
            | nibbles[3],
            compare=(nibbles[4] << 4) | nibbles[5],
            replace=(nibbles[6] << 4) | nibbles[7],
        )


class MemoryBus:
    """Flat byte-addressable memory. The cartridge wraps reads; pokes bypass it."""

    def __init__(self, size: int = 0x10000) -> None:
        if size <= 0:
            raise ValueError("size must be positive")
        self._mem = bytearray(size)

    @property
    def size(self) -> int:
        return len(self._mem)

    def poke(self, address: int, value: int) -> None:
        """Direct write, bypassing any patches (setting up the 'cartridge')."""
        self._check(address)
        self._mem[address] = value & 0xFF

    def raw_read(self, address: int) -> int:
        self._check(address)
        return self._mem[address]

    def _check(self, address: int) -> None:
        if not (0 <= address < len(self._mem)):
            raise IndexError(f"address {address:#x} out of range")


@dataclass
class Dial:
    """A named difficulty dial: a plain-language label plus the codes behind it."""

    name: str
    blurb: str
    codes: List[PatchCode] = field(default_factory=list)


class CheatCartridge:
    """Pass-through patch layer: intercepts reads, compare-and-replaces."""

    def __init__(self, bus: MemoryBus) -> None:
        self.bus = bus
        self.codes: List[PatchCode] = []
        self.fired: List[str] = []  # log of substitutions actually applied

    def add(self, code: PatchCode) -> None:
        if code not in self.codes:
            self.codes.append(code)

    def remove(self, code: PatchCode) -> bool:
        if code in self.codes:
            self.codes.remove(code)
            return True
        return False

    def read(self, address: int) -> int:
        """Read through the cartridge: first matching compare wins."""
        actual = self.bus.raw_read(address)
        for code in self.codes:
            if code.address == address and actual == code.compare:
                self.fired.append(
                    f"{code.encode()}: mem[{address:#06x}] {actual:#04x}->{code.replace:#04x}"
                )
                return code.replace
        return actual

    def apply_dial(self, dial: Dial) -> None:
        for code in dial.codes:
            self.add(code)

    def clear(self) -> None:
        self.codes.clear()
        self.fired.clear()


def _p(addr: int, compare: int, replace: int) -> PatchCode:
    return PatchCode(address=addr, compare=compare, replace=replace)


# Preset difficulty dials over a fictional game memory map:
#   0x00FF lives counter (starts at 3), 0x0100 damage per hit (starts 1),
#   0x0101 score multiplier (starts 1), 0x0102 timer seconds (starts 60).
DIALS: Dict[str, Dial] = {
    "infinite_lives": Dial(
        name="infinite_lives",
        blurb="Lives never drop below 3: any decrement read is replaced.",
        codes=[_p(0x00FF, 2, 3), _p(0x00FF, 1, 3), _p(0x00FF, 0, 3)],
    ),
    "gentle_hits": Dial(
        name="gentle_hits",
        blurb="Damage per hit reads as 1 even when the game raises it.",
        codes=[_p(0x0100, 2, 1), _p(0x0100, 3, 1), _p(0x0100, 4, 1)],
    ),
    "double_score": Dial(
        name="double_score",
        blurb="Score multiplier reads as 2.",
        codes=[_p(0x0101, 1, 2)],
    ),
    "slow_timer": Dial(
        name="slow_timer",
        blurb="Timer ticks read back 10s higher (compare 50 -> 60).",
        codes=[_p(0x0102, 50, 60)],
    ),
}


def list_dials() -> List[str]:
    """Names of the built-in difficulty dials."""
    return sorted(DIALS)
