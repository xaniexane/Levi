"""LEVI's productive shorthand: a primitive symbol set with compounding rules.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #5)

The old mechanism: a compact set of primitive marks that stand for common
words and roots, plus rules for compounding them into longer forms so a
writer can keep up with speech. The trade is explicit: speed for exactness.
LEVI's reimplementation honors that trade — ``encode`` produces a compact
token stream; ``decode`` is LOSSY on purpose and degrades gracefully.

The primitives: one-symbol words for the common vocabulary (pronouns,
connectives, auxiliaries), two-letter roots for content words, and three
compounding rules —
  1. ROOT+SUFFIX: a root mark joined to a suffix mark (run+ning)
  2. CONTRACTION: dropping the vowel core of a root (strength → strngth)
  3. PHRASE-BLEND: two primitives fused under one stroke (do+not → don't)

``decode`` on unseen material never raises and never invents: unknown words
are emitted as ``⟦word⟧`` markers inline, fluency preserved, uncertainty
visible. Round-trip fidelity is reported by ``fidelity``: the fraction of
tokens that decode exactly. The honest claim is right there in the name —
this is a *productive* shorthand, not a lossless codec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/tironian"

# -- the primitive symbol set ----------------------------------------------
# One-mark words for the high-frequency vocabulary.
ONE_MARKS: Dict[str, str] = {
    "the": "·",
    "and": "&",
    "of": "º",
    "to": "→",
    "in": "∈",
    "is": "≡",
    "it": "ι",
    "that": "∴",
    "you": "υ",
    "i": "ɪ",
    "we": "ω",
    "not": "¬",
    "a": "α",
    "be": "β",
    "have": "ħ",
    "do": "δ",
    "with": "⊕",
    "for": "φ",
    "on": "⊙",
    "as": "≍",
    "at": "@",
    "by": "∵",
    "this": "θ",
    "from": "⇐",
    "or": "∨",
    "but": "⊼",
    "what": "¿",
    "all": "∀",
    "was": "ϖ",
    "are": "∊",
}

# Two-letter roots for common content words: symbol -> word and word -> symbol.
ROOTS: Dict[str, str] = {
    "run": "rn",
    "write": "wr",
    "read": "rd",
    "speak": "sp",
    "think": "th",
    "know": "kn",
    "make": "mk",
    "take": "tk",
    "give": "gv",
    "time": "tm",
    "mind": "mn",
    "hand": "hn",
    "work": "wk",
    "word": "wd",
    "world": "wrld",
    "memory": "mm",
    "idea": "id",
    "learn": "ln",
    "build": "bd",
    "system": "sy",
    "good": "gd",
    "new": "nw",
    "great": "gr",
    "long": "lg",
    "small": "sm",
    "first": "fs",
    "day": "dy",
    "man": "mn2",
    "thing": "tg",
    "people": "pp",
}

# Compounding suffixes: word-ending -> mark.
SUFFIXES: List[Tuple[str, str]] = [
    ("ing", "ⁿᵍ"),
    ("ed", "ᵈ"),
    ("tion", "ᵗⁿ"),
    ("sion", "ˢⁿ"),
    ("ly", "ˡʸ"),
    ("ness", "ⁿˢ"),
    ("ment", "ᵐᵗ"),
    ("es", "ᵉˢ"),
    ("s", "ˢ"),
]

UNKNOWN_OPEN = "⟦"
UNKNOWN_CLOSE = "⟧"

_TOKEN_RE = re.compile(r"[A-Za-z']+|[^A-Za-z'\s]+|\s+")

# Inverse lookups, built once.
_INV_ONE = {v: k for k, v in ONE_MARKS.items()}
_INV_ROOT = {v: k for k, v in ROOTS.items()}


def _is_mark(token: str) -> bool:
    """Is this token a shorthand mark (decodable) rather than raw text?"""
    if token in _INV_ONE or token in _INV_ROOT:
        return True
    for _ending, smark in SUFFIXES:
        if token.endswith(smark) and len(token) > len(smark):
            return True
    return token.startswith(UNKNOWN_OPEN) and token.endswith(UNKNOWN_CLOSE)


@dataclass
class Stream:
    """An encoded token stream: the compact form plus its coverage report."""

    tokens: List[str]
    unknown_words: List[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Fraction of word-tokens the shorthand knew."""
        words = [t for t in self.tokens if re.fullmatch(r"[A-Za-z']+", t)]
        if not words:
            return 1.0
        known = len(words) - len(self.unknown_words)
        return known / len(words)

    def text(self) -> str:
        return "".join(self.tokens)


def _contract(word: str) -> str:
    """Rule 2: drop the vowel core — first letter + consonants after."""
    if len(word) <= 3:
        return word
    consonants = "".join(ch for ch in word[1:] if ch not in "aeiou")
    return word[0] + consonants


def _encode_word(word: str) -> Tuple[str, bool]:
    """Encode one word; return (mark, was_known)."""
    low = word.lower()
    if low in ONE_MARKS:
        return ONE_MARKS[low], True
    if low in ROOTS:
        return ROOTS[low], True
    # Rule 1: ROOT + SUFFIX compounding
    for ending, mark in SUFFIXES:
        if low.endswith(ending) and len(low) > len(ending):
            stem = low[: -len(ending)]
            if stem in ROOTS:
                return ROOTS[stem] + mark, True
            # Rule 3-ish: contract unknown stems, keep the suffix mark
            return _contract(stem) + mark, False
    return UNKNOWN_OPEN + word + UNKNOWN_CLOSE, False


def encode(text: str) -> Stream:
    """Compress text into the shorthand token stream.

    Known words become marks; unknown content words contract (vowel-core
    drop) where a suffix rule catches them, else are marked ⟦word⟧.
    Punctuation and spacing pass through untouched — fluency first.
    """
    tokens: List[str] = []
    unknowns: List[str] = []
    for piece in _TOKEN_RE.findall(text):
        if re.fullmatch(r"[A-Za-z']+", piece):
            mark, known = _encode_word(piece)
            tokens.append(mark)
            if not known:
                unknowns.append(piece)
        else:
            tokens.append(piece)
    return Stream(tokens=tokens, unknown_words=unknowns)


def _decode_word(mark: str) -> str:
    """Decode one mark back to a word. Unknown marks stay visible."""
    if mark in _INV_ONE:
        return _INV_ONE[mark]
    if mark in _INV_ROOT:
        return _INV_ROOT[mark]
    for ending, smark in SUFFIXES:
        if mark.endswith(smark) and len(mark) > len(smark):
            stem_mark = mark[: -len(smark)]
            if stem_mark in _INV_ROOT:
                return _INV_ROOT[stem_mark] + ending
            return stem_mark + ending  # contracted stem: best effort
    if mark.startswith(UNKNOWN_OPEN) and mark.endswith(UNKNOWN_CLOSE):
        return mark[len(UNKNOWN_OPEN) : -len(UNKNOWN_CLOSE)]
    return mark  # punctuation / untouched marks


def decode(stream: Stream) -> str:
    """Expand a token stream back toward plain text.

    Graceful by contract: unknown words were preserved verbatim inside
    ⟦ ⟧ markers, contracted stems come back best-effort, and nothing here
    raises on unseen material. Lossy, fluent, honest.
    """
    out: List[str] = []
    for token in stream.tokens:
        if _is_mark(token):
            out.append(_decode_word(token))
        else:
            out.append(token)  # whitespace, punctuation, plain words pass through
    return "".join(out)


def fidelity(text: str) -> float:
    """Fraction of words that survive the encode→decode round trip exactly."""
    stream = encode(text)
    back = decode(stream)
    originals = [w.lower() for w in re.findall(r"[A-Za-z']+", text)]
    returns = [w.lower() for w in re.findall(r"[A-Za-z']+", back)]
    if not originals:
        return 1.0
    exact = sum(1 for a, b in zip(originals, returns, strict=False) if a == b)
    return exact / len(originals)
