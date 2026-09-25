"""Constrained alphabet: narrow the input space, gain reliability.

Origin: Palm Graffiti (1990s). Palm's rivals chased natural handwriting
recognition and failed; Palm shipped a prescribed single-stroke shorthand
alphabet that users learned in about twenty minutes — one stroke per
character, stroke end = character commit — and claimed near-100% accuracy.
Palm deliberately made the human adapt a little so the machine could be
exact: constrain the input space instead of expanding the recognizer.

What it is in LEVI: ``ConstrainedAlphabet``. A small, fixed, unambiguous
token set — one prescribed stroke per character. ``parse`` accepts only exact
tokens; anything else — an unknown token, a near-miss, the same token in the
wrong case — raises instead of being guessed. There is deliberately no
"did you mean"; ambiguity is eliminated at the source, not resolved by
inference.

Honesty label: LOAD-BEARING — exact-match parsing with no fuzzy fallback is a
concrete, enforceable discipline.

Deny-closed inputs: empty stroke sets, empty stroke tokens, tokens that
differ only by case, duplicate tokens, tokens mapped to anything but exactly
one character, two tokens mapped to the same character, empty parse input,
and any token that is not a prescribed stroke are all rejected with
ValueError.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["DEFAULT_STROKES", "ConstrainedAlphabet"]

DEFAULT_STROKES: dict[str, str] = {
    "lambda": "A",  # the Graffiti A: an upside-down V without crossbar
    "belly": "B",
    "open-left": "C",
    "belly-mirror": "D",
    "rake": "E",
    "rake-top": "F",
    "open-left-hook": "G",
    "ladder": "H",
    "post": "I",
    "hook": "J",
    "fork": "K",
    "corner": "L",
    "twin-peaks": "M",
    "zig": "N",
    "loop": "O",
    "flag": "P",
    "loop-tail": "Q",
    "flag-leg": "R",
    "ess": "S",
    "tee": "T",
    "cup": "U",
    "vee": "V",
    "twin-cups": "W",
    "cross": "X",
    "sling": "Y",
    "zet": "Z",
}


class ConstrainedAlphabet:
    """One prescribed stroke per character; parse() is exact or it fails."""

    def __init__(self, strokes: Optional[dict[str, str]] = None) -> None:
        table = dict(strokes) if strokes is not None else dict(DEFAULT_STROKES)
        if not table:
            raise ValueError("a constrained alphabet needs at least one stroke")
        for token, char in table.items():
            if not isinstance(token, str) or not token.strip():
                raise ValueError("stroke tokens must be non-empty strings")
            if not isinstance(char, str) or len(char) != 1:
                raise ValueError(
                    f"stroke {token!r}: must map to exactly one character, got {char!r}"
                )
        if len(set(table.values())) != len(table):
            raise ValueError(
                "strokes must be one-to-one: two strokes map to the same character"
            )
        lowered = [t.lower() for t in table]
        if len(set(lowered)) != len(lowered):
            raise ValueError(
                "strokes must not differ only by case — the set would be ambiguous"
            )
        self._table = table

    def parse(self, strokes: str) -> str:
        """Translate a whitespace-separated stroke string into characters.

        Exact tokens only. A near-miss, a wrong-case token, or anything else
        unprescribed raises — it is never guessed.
        """
        if not isinstance(strokes, str) or not strokes.strip():
            raise ValueError("parse needs a non-empty stroke string")
        out: list[str] = []
        for token in strokes.split():
            if token not in self._table:
                raise ValueError(
                    f"unknown stroke {token!r}: no guessing — use a prescribed stroke"
                )
            out.append(self._table[token])
        return "".join(out)

    def add_stroke(self, token: str, char: str) -> None:
        """Prescribe a new stroke. The constraints apply here too."""
        if not isinstance(token, str) or not token.strip():
            raise ValueError("stroke token must be a non-empty string")
        if token in self._table:
            raise ValueError(f"duplicate stroke: {token!r}")
        if token.lower() in (t.lower() for t in self._table):
            raise ValueError(
                f"stroke {token!r} differs only by case from an existing stroke"
            )
        if not isinstance(char, str) or len(char) != 1:
            raise ValueError(
                f"stroke {token!r}: must map to exactly one character, got {char!r}"
            )
        if char in self._table.values():
            raise ValueError(f"character {char!r} already has a prescribed stroke")
        self._table[token] = char

    def strokes(self) -> list[str]:
        """The prescribed stroke set, in definition order."""
        return list(self._table)

    def char_for(self, token: str) -> str:
        """Look up one stroke exactly. Unknown tokens raise."""
        if token not in self._table:
            raise ValueError(
                f"unknown stroke {token!r}: no guessing — use a prescribed stroke"
            )
        return self._table[token]
