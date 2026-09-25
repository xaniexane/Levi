"""Tamper-evident accounting from sealed tokens and impressed tablets.

Studied from: pre-digital-computation-20260916/report.md [Beat C #8]
(Clay-tablet accounting, Uruk, 4th millennium BCE)

The studied shape: counters are kept as tokens sealed inside a clay
bulla — the seal is a checksum, and verification means breaking the
bulla and comparing the contents against the seal's record. Destruction
is the verification method. Later the tokens' impressions are pressed
into the tablet surface itself, and the impressed marks become numerals:
the counting pipeline invents numbers as a side effect.

LEVI-native re-expression: a **Bulla** holds tokens and a seal digest
computed over their canonical record; **verify** breaks the bulla
(marks it broken) and recomputes the digest — mismatch means tampering,
and a bulla can only be verified once; **impress** turns a token batch
into a **Tablet** of impressed count-marks per commodity, and **read**
decodes the marks back to counts. The seal uses SHA-256 over a
canonical string, which is the honest modern analogue of the clay seal.

Operations:

* ``Token(shape, commodity)`` / ``Bulla(tokens)`` / ``bulla.seal()`` -> seal digest
* ``bulla.verify(seal_record)`` -> True/False; breaks the bulla (single-use)
* ``impress(tokens)`` -> Tablet; ``tablet.read()`` -> {commodity: count}

Honest limits: SHA-256 stands in for a clay seal — it detects
tampering, it does not authenticate the sealer. Impressed marks encode
counts only, not the shapes of the tokens that produced them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/clay-accounting"


@dataclass(frozen=True)
class Token:
    """One counting token: a shape standing for one unit of a commodity."""

    shape: str
    commodity: str


def _canonical_record(tokens: List[Token]) -> str:
    items = sorted(f"{t.shape}:{t.commodity}" for t in tokens)
    return "|".join(items)


def _digest(record: str) -> str:
    return hashlib.sha256(record.encode("utf-8")).hexdigest()


class Bulla:
    """A sealed envelope of tokens. Verification breaks the seal: single-use."""

    def __init__(self, tokens: List[Token]) -> None:
        if not tokens:
            raise ValueError("a bulla must contain at least one token")
        self._tokens: List[Token] = list(tokens)
        self._record = _canonical_record(self._tokens)
        self._broken = False

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    @property
    def broken(self) -> bool:
        return self._broken

    def seal(self) -> str:
        """Press the seal: the digest of the tokens' canonical record."""
        return _digest(self._record)

    def tamper(self, token: Token) -> None:
        """Simulate tampering: swap one token. Only possible before sealing/verification."""
        if self._broken:
            raise RuntimeError("cannot tamper with an already-broken bulla")
        self._tokens[0] = token
        self._record = _canonical_record(self._tokens)

    def verify(self, seal_record: str) -> bool:
        """Break the bulla and compare contents against the seal record.

        Returns True when the contents match the seal (untampered),
        False otherwise. Can only be called once.
        """
        if self._broken:
            raise RuntimeError("bulla already broken: verification is single-use")
        self._broken = True
        return _digest(self._record) == seal_record


@dataclass
class Tablet:
    """Impressed marks: commodity -> count, the token impressions made visible."""

    marks: Dict[str, int] = field(default_factory=dict)

    def read(self) -> Dict[str, int]:
        """Decode the impressed marks back into commodity counts."""
        return dict(self.marks)

    def total(self) -> int:
        return sum(self.marks.values())


def impress(tokens: List[Token]) -> Tablet:
    """Press tokens into a tablet surface: shapes become count-marks per commodity."""
    if not tokens:
        raise ValueError("cannot impress an empty token batch")
    marks: Dict[str, int] = {}
    for token in tokens:
        marks[token.commodity] = marks.get(token.commodity, 0) + 1
    return Tablet(marks=marks)
