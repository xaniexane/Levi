"""Chorded keyset input: the whole alphabet in five keys, no hand travel.

Origin: Douglas Engelbart's five-key coding keyset, demonstrated with the
NLS at the 1968 "Mother of All Demos" (SRI Augmentation Research Center).
The keyset sat under the left hand while the right hand held the mouse —
typing without lifting the hand off the pointing device or the eyes off
the screen. The mouse lived; the keyset died of its learning curve.

The mechanism, faithfully kept:
- Five keys with bit values 1, 2, 4, 8, 16. A chord is the SUM of the
  depressed keys: a=1, b=2, c=3 (1+2), ... z=26. 31 combinations cover the
  alphabet plus five punctuation marks.
- Release-register: the character is NOT registered until the last
  depressed key is released. A chord may be rolled (press 1, press 2,
  release 1, release 2) — the result depends only on the SET of keys in
  the stroke, never on order or timing.
- In NLS the mouse buttons were modifiers (middle = uppercase, left =
  numbers/punctuation). Here that is a configurable shift layer.

What it is in LEVI: ``ChordKeyer``. Clean-room, stdlib-only, local-first.
Engelbart's letter mapping (1..26 -> a..z) is kept verbatim; the five
punctuation assignments (27..31) are a documented reconstruction — the
sources confirm the punctuation SET, not which chord carried which mark.
Honest use: a one-handed entry protocol for LEVI's phone-first keeper
(five screen zones or button chords under one hand, the other hand free).

LAWS (declared before implementation; the proof is tests/test_chord.py):
1. TOTALITY — every 5-bit chord in 1..31 maps to exactly one symbol;
   the empty chord (no keys) is rejected with ValueError, never silent.
2. ORDER-INDEPENDENCE — a stroke's symbol depends only on the SET of
   keys depressed, not on press/release order or timing.
3. ROUND-TRIP — encode(symbol) -> stroke -> decode(stroke) == symbol
   for every encodable symbol.
4. TRAINER HONESTY — the trainer accepts only exact strokes and reports
   each miss with the expected chord; it never auto-corrects.

Honesty label: LOAD-BEARING — the binary chord map and release-register
rule are the concrete mechanism. The honest claim is narrow: input
without hand travel, one-handed, alongside a pointing device — not a
replacement for touch-typing.

Deny-closed inputs: keys outside {1,2,4,8,16}, empty strokes, unknown
symbols, and non-set stroke inputs are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Sequence, Tuple

__all__ = ["ChordKeyer", "KeyerTrainer", "KEYS", "chord_sum", "encode", "decode"]

KEYS: Tuple[int, ...] = (1, 2, 4, 8, 16)
"""The five key bit-values, Engelbart's original mapping."""


def _build_table() -> Dict[int, str]:
    table: Dict[int, str] = {}
    for n in range(1, 27):
        table[n] = chr(ord("a") + n - 1)
    # Reconstruction: sources confirm these five marks lived in 27..31,
    # but not which chord carried which mark. Assignment is ours.
    table[27] = " "
    table[28] = "."
    table[29] = ","
    table[30] = ";"
    table[31] = "?"
    return table


_CHORD_TO_SYMBOL: Dict[int, str] = _build_table()
_SYMBOL_TO_CHORD: Dict[str, int] = {s: c for c, s in _CHORD_TO_SYMBOL.items()}


def chord_sum(keys: Iterable[int]) -> int:
    """Sum the bit-values of a stroke's key set (deny-closed)."""
    total = 0
    seen = set()
    for k in keys:
        if k not in KEYS:
            raise ValueError("unknown key %r: keys are %s" % (k, KEYS))
        if k in seen:
            raise ValueError("duplicate key %r in stroke" % (k,))
        seen.add(k)
        total += k
    if total == 0:
        raise ValueError("empty stroke registers nothing")
    return total


def decode(keys: Iterable[int]) -> str:
    """Register a stroke: the set of depressed keys -> the symbol."""
    return _CHORD_TO_SYMBOL[chord_sum(keys)]


def encode(symbol: str) -> FrozenSet[int]:
    """The key set that produces ``symbol`` (deny-closed)."""
    try:
        total = _SYMBOL_TO_CHORD[symbol]
    except KeyError:
        raise ValueError("no chord for symbol %r" % (symbol,)) from None
    return frozenset(k for k in KEYS if total & k)


@dataclass
class KeyerTrainer:
    """Rehearsal harness: drill strokes, score exact matches, report misses.

    Never auto-corrects: a miss is reported with the expected chord so
    the learner rehearses the right gesture.
    """

    attempts: int = 0
    correct: int = 0
    misses: List[Tuple[str, FrozenSet[int], FrozenSet[int]]] = field(
        default_factory=list
    )
    """(target_symbol, expected_chord, attempted_chord) for each miss."""

    def attempt(self, target: str, keys: Iterable[int]) -> bool:
        """Score one stroke against its target. Returns True on exact hit."""
        expected = encode(target)  # deny-closed: unknown targets rejected
        got = frozenset(keys)
        for k in got:
            if k not in KEYS:
                raise ValueError("unknown key %r: keys are %s" % (k, KEYS))
        self.attempts += 1
        if got == expected and decode(got) == target:
            self.correct += 1
            return True
        self.misses.append((target, expected, got))
        return False

    def drill(self, text: str) -> List[FrozenSet[int]]:
        """The expected chord sequence for ``text`` (the lesson plan)."""
        return [encode(ch) for ch in text]

    @property
    def accuracy(self) -> float:
        """Fraction correct; 0.0 before any attempt (never a fake 100%)."""
        if self.attempts == 0:
            return 0.0
        return self.correct / self.attempts


class ChordKeyer:
    """A live keyset: press keys, release them, register strokes.

    Models the release-register rule: ``release`` of the last depressed
    key completes the stroke and returns its symbol. Partial releases
    return None — the stroke is not yet registered.
    """

    def __init__(self) -> None:
        self._down: List[int] = []
        self._stroke: List[int] = []

    def press(self, key: int) -> None:
        """Depress a key (deny-closed on unknown/double-press)."""
        if key not in KEYS:
            raise ValueError("unknown key %r: keys are %s" % (key, KEYS))
        if key in self._down:
            raise ValueError("key %r already depressed" % (key,))
        self._down.append(key)
        if key not in self._stroke:
            self._stroke.append(key)

    def release(self, key: int) -> str | None:
        """Release a key. Returns the symbol when the stroke completes."""
        if key not in self._down:
            raise ValueError("key %r was not depressed" % (key,))
        self._down.remove(key)
        if self._down:
            return None
        stroke, self._stroke = self._stroke, []
        return decode(stroke)

    def type_text(self, text: str) -> List[FrozenSet[int]]:
        """Encode text as a stroke sequence (the lesson, not the typing)."""
        return [encode(ch) for ch in text]
