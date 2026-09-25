"""LEVI's decimal survey chain: 100 links to the chain, 10 square chains to the acre.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(Gunter's Chain / Furlong-Rod-Acre)

The studied mechanism: a 66-foot chain of 100 links made land measure
*compute-friendly*. Because the chain was decimal (100 links) and the
acre was defined as exactly 10 square chains, area arithmetic collapsed
to moving a decimal point: measure a rectangle in chains, multiply,
divide by ten — acres, with no awkward fractions. The ladder (links →
chains → furlongs → miles; square chains → acres) was designed so the
math stays clean at every rung.

This module rebuilds that as LEVI's own mechanism. :class:`Chain` is a
length expressed in links — the atomic unit — with exact conversions up
the ladder. :func:`acres` computes a rectangle's area in acres from
chain-denominated sides using :class:`~fractions.Fraction`, so "10
square chains = 1 acre exactly" is exact, not floating-point close.
:func:`ladder` renders any length as the full rung-by-rung breakdown,
and :func:`parse_links` reads the surveyor's shorthand ("3 chains 25
links").

Honest limits: the module models the *arithmetic* of the chain, not
field craft — it cannot tell you whether your chain is stretched, your
ground level, or your line straight. Garbage measurements in, exact
arithmetic on garbage out.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/gunter_chain"

# The ladder, in links. A link is the atomic unit; everything else is
# an exact multiple of it.
LINKS_PER_CHAIN = 100
CHAINS_PER_FURLONG = 10
FURLONGS_PER_MILE = 8
SQUARE_CHAINS_PER_ACRE = 10
FEET_PER_LINK = Fraction(66, 100)  # the chain is 66 feet of 100 links

_RUNG_LINKS: List[Tuple[str, int]] = [
    ("link", 1),
    ("chain", LINKS_PER_CHAIN),
    ("furlong", LINKS_PER_CHAIN * CHAINS_PER_FURLONG),
    ("mile", LINKS_PER_CHAIN * CHAINS_PER_FURLONG * FURLONGS_PER_MILE),
]


class ChainError(Exception):
    """Base error for chain-arithmetic failures."""


@dataclass(frozen=True)
class Chain:
    """A length, stored exactly as a whole number of links."""

    links: int

    def __post_init__(self) -> None:
        if self.links < 0:
            raise ChainError("a chain length cannot be negative")

    @classmethod
    def from_chains(cls, chains: float) -> "Chain":
        """From a decimal chain count (e.g. 2.5 chains = 250 links)."""
        links = round(chains * LINKS_PER_CHAIN)
        if abs(links - chains * LINKS_PER_CHAIN) > 1e-9:
            raise ChainError(f"{chains} chains is not a whole number of links")
        return cls(links)

    @property
    def chains(self) -> Fraction:
        return Fraction(self.links, LINKS_PER_CHAIN)

    @property
    def feet(self) -> Fraction:
        return Fraction(self.links) * FEET_PER_LINK

    def __add__(self, other: "Chain") -> "Chain":
        if not isinstance(other, Chain):
            return NotImplemented
        return Chain(self.links + other.links)

    def __sub__(self, other: "Chain") -> "Chain":
        if not isinstance(other, Chain):
            return NotImplemented
        return Chain(self.links - other.links)

    def __mul__(self, factor: int) -> "Chain":
        return Chain(self.links * factor)


def acres(length: Chain, width: Chain) -> Fraction:
    """Area of a rectangle in acres, exactly.

    length × width in square chains, divided by 10 square chains per
    acre — the decimal trick that made the chain compute-friendly.
    """
    square_chains = length.chains * width.chains
    return square_chains / SQUARE_CHAINS_PER_ACRE


def square_chains(length: Chain, width: Chain) -> Fraction:
    """Area of a rectangle in square chains, exactly."""
    return length.chains * width.chains


def ladder(length: Chain) -> Dict[str, Fraction]:
    """The full measurement ladder for a length: link → chain → furlong → mile."""
    return {name: Fraction(length.links, per) for name, per in _RUNG_LINKS}


def parse_links(text: str) -> Chain:
    """Read the surveyor's shorthand: "3 chains 25 links", "2 furlongs", "40 links".

    Accepts any combination of the rung names (singular or plural),
    space-separated pairs of <number> <rung>.
    """
    words = text.lower().replace(",", " ").split()
    if len(words) % 2 != 0:
        raise ChainError(f"cannot parse {text!r}: expected <number> <unit> pairs")
    if len(words) % 2 != 0:
        raise ChainError(f"cannot parse {text!r}: expected <number> <unit> pairs")
    rung_lookup = {name: per for name, per in _RUNG_LINKS}
    rung_lookup.update({name + "s": per for name, per in _RUNG_LINKS})
    total = 0
    for number, rung in zip(words[0::2], words[1::2], strict=True):
        if rung not in rung_lookup:
            raise ChainError(f"unknown rung {rung!r} in {text!r}")
        try:
            count = int(number)
        except ValueError:
            raise ChainError(f"not a whole number: {number!r} in {text!r}") from None
        total += count * rung_lookup[rung]
    return Chain(total)
