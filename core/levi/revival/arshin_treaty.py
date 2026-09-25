"""LEVI's treaty peg: bilateral metrological agreements anchored by treaty, not decree.

Studied from: lost-crafts-20260916/report.md [Batch 2] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: when two measure-systems must interoperate,
the parties ratify a *treaty peg* — an immutable, hash-linked record fixing the
ratio between one unit on each side (here: the arshin pegged to 28 English
inches). Every conversion between the two systems routes through the ratified
peg, so a party can no longer quietly redefine its own unit: ``audit()``
compares each side's current working definition against the peg and reports
*drift* as a treaty violation. The peg chain itself is append-only and
self-verifying.

Honesty: BOOKKEEPING, not metrology. The registry records what was ratified,
converts through those records, and flags inconsistencies. It cannot verify
that any physical artifact actually measured what the treaty claims — the
hardware anchor is outside the code.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/arshin-treaty"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """A working definition of one unit: how many inches it currently claims."""

    name: str
    system: str
    inches: float


@dataclass(frozen=True)
class TreatyPeg:
    """One ratified bilateral peg. Immutable; hash-linked to the previous peg."""

    seq: int
    party_a: str
    party_b: str
    unit_a: str
    unit_b: str
    ratio_a_per_b: float  # fixed: 1 unit_a == ratio_a_per_b unit_b
    prev_digest: str
    digest: str


@dataclass(frozen=True)
class Violation:
    """A peg whose current working definitions no longer match the treaty."""

    peg_seq: int
    unit_a: str
    unit_b: str
    treaty_ratio: float
    current_ratio: float
    drift: float  # relative drift, |current - treaty| / treaty


def _peg_digest(
    seq: int,
    party_a: str,
    party_b: str,
    unit_a: str,
    unit_b: str,
    ratio: float,
    prev: str,
) -> str:
    body = f"{seq}|{party_a}|{party_b}|{unit_a}|{unit_b}|{ratio!r}|{prev}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TreatyRegistry:
    """Units, their working definitions, and the treaty pegs between systems.

    Conversions *within* one system use each unit's declared inches. A
    conversion *across* systems routes through the treaty peg if one exists
    between those two units; otherwise it falls back to the declared inches
    of both sides (marked as unpegged).
    """

    def __init__(self) -> None:
        self._units: Dict[str, Unit] = {}
        self._pegs: List[TreatyPeg] = []

    # -- definitions -------------------------------------------------------
    def define_unit(self, name: str, system: str, inches: float) -> Unit:
        """Declare (or quietly redefine) a working definition for ``name``.

        Redefinition is exactly what ``audit()`` watches for: the treaty peg
        does not move, so a redefined unit shows up as drift.
        """
        if inches <= 0:
            raise ValueError("inches must be positive")
        unit = Unit(name=name, system=system, inches=inches)
        self._units[name] = unit
        return unit

    def unit(self, name: str) -> Unit:
        return self._units[name]

    # -- treaty pegs --------------------------------------------------------
    def ratify(
        self,
        party_a: str,
        party_b: str,
        unit_a: str,
        unit_b: str,
        ratio_a_per_b: float,
    ) -> TreatyPeg:
        """Fix the ratio ``1 unit_a == ratio_a_per_b unit_b`` forever.

        Both units must already be defined. The peg is appended to the
        hash-linked chain; there is no API for editing or removing one.
        """
        if unit_a not in self._units or unit_b not in self._units:
            raise KeyError("both pegged units must be defined first")
        if ratio_a_per_b <= 0:
            raise ValueError("ratio must be positive")
        seq = len(self._pegs)
        prev = self._pegs[-1].digest if self._pegs else "GENESIS"
        digest = _peg_digest(seq, party_a, party_b, unit_a, unit_b, ratio_a_per_b, prev)
        peg = TreatyPeg(
            seq=seq,
            party_a=party_a,
            party_b=party_b,
            unit_a=unit_a,
            unit_b=unit_b,
            ratio_a_per_b=ratio_a_per_b,
            prev_digest=prev,
            digest=digest,
        )
        self._pegs.append(peg)
        return peg

    def pegs(self) -> Tuple[TreatyPeg, ...]:
        return tuple(self._pegs)

    def verify_pegs(self) -> bool:
        """Recompute the hash chain. False means the treaty log was tampered with."""
        prev = "GENESIS"
        for peg in self._pegs:
            want = _peg_digest(
                peg.seq,
                peg.party_a,
                peg.party_b,
                peg.unit_a,
                peg.unit_b,
                peg.ratio_a_per_b,
                prev,
            )
            if want != peg.digest or peg.prev_digest != prev:
                return False
            prev = peg.digest
        return True

    # -- conversion ----------------------------------------------------------
    def _peg_between(self, a: str, b: str) -> Optional[TreatyPeg]:
        for peg in self._pegs:
            if {peg.unit_a, peg.unit_b} == {a, b}:
                return peg
        return None

    def convert(self, value: float, from_unit: str, to_unit: str) -> Tuple[float, bool]:
        """Convert ``value`` from one unit to another.

        Returns ``(result, pegged)`` where ``pegged`` is True when a treaty
        peg governed the crossing (rather than raw declared inches).
        """
        if from_unit == to_unit:
            return value, False
        ua = self._units[from_unit]
        ub = self._units[to_unit]
        peg = self._peg_between(from_unit, to_unit)
        if peg is not None:
            # Route through the treaty ratio, not the local definitions.
            if from_unit == peg.unit_a:
                # value in unit_a -> unit_b: 1 unit_a == ratio unit_b
                return value * peg.ratio_a_per_b, True
            return value / peg.ratio_a_per_b, True
        # Unpegged: convert via each side's declared inches.
        inches = value * ua.inches
        return inches / ub.inches, False

    # -- audit ----------------------------------------------------------------
    def audit(self, tolerance: float = 1e-9) -> List[Violation]:
        """Compare every peg against the parties' *current* working definitions.

        If a side has redefined its unit since ratification, the implied
        ratio drifts from the treaty ratio and a Violation is reported.
        """
        violations: List[Violation] = []
        for peg in self._pegs:
            ua = self._units[peg.unit_a]
            ub = self._units[peg.unit_b]
            # Current implied ratio: 1 unit_a == (ua.inches / ub.inches) unit_b.
            current = ua.inches / ub.inches
            drift = abs(current - peg.ratio_a_per_b) / peg.ratio_a_per_b
            if drift > tolerance:
                violations.append(
                    Violation(
                        peg_seq=peg.seq,
                        unit_a=peg.unit_a,
                        unit_b=peg.unit_b,
                        treaty_ratio=peg.ratio_a_per_b,
                        current_ratio=current,
                        drift=drift,
                    )
                )
        return violations


# ---------------------------------------------------------------------------
# A ready-made arshin treaty for the tests and demos
# ---------------------------------------------------------------------------


def arshin_treaty_registry() -> TreatyRegistry:
    """Build the canonical demo: arshin pegged to 28 English inches."""
    reg = TreatyRegistry()
    reg.define_unit("english_inch", "english", 1.0)
    reg.define_unit("english_foot", "english", 12.0)
    reg.define_unit("arshin", "russian", 28.0)
    reg.define_unit("sazhen", "russian", 84.0)  # 3 arshin
    reg.define_unit("verst", "russian", 42000.0)  # 1500 arshin
    reg.ratify("russian_guild", "english_guild", "arshin", "english_inch", 28.0)
    return reg
