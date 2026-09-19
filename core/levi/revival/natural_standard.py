"""LEVI's self-replicating measure: a standard anyone can re-derive in the field.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(Barleycorn Inch)

The studied mechanism: instead of guarding one precious bar, define the
unit from *N copies of a common natural object* — three barleycorns to
the inch. Anyone, anywhere, can grow the reference, lay N in a row, and
audit the measure themselves. No vault, no keeper, no chain of trust:
the standard replicates wherever the crop grows. The same trick
bootstrapped grading — shoe sizes as multiples of the corn.

This module rebuilds that as LEVI's own mechanism. A
:class:`NaturalStandard` declares: ``copies`` of ``reference_object``
equal one unit. Because nature varies, the module never pretends the
reference is exact: :meth:`NaturalStandard.calibrate` takes a field
sample, reports mean / spread / standard error, and only *adopts* the
sample's mean as the working value when the spread is within a declared
tolerance. :meth:`grade` builds stepped sizes (the shoe-size trick) as
integer multiples, and :meth:`audit` re-checks a fresh sample against
the adopted value.

Honest limits: this is honest *about* uncertainty rather than exact.
A software module cannot grow barley; the "samples" are numbers the
caller measured. The module's real work is the statistics and the
quorum rule: refuse to adopt a standard whose samples disagree too
much, and say so plainly.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple


ORIGIN = "levi-revival/natural_standard"


class NaturalStandardError(Exception):
    """Base error for natural-standard failures."""


@dataclass
class Calibration:
    """The outcome of deriving the unit from a field sample."""

    sample_size: int
    mean: float  # adopted value of one reference object, in base units
    stdev: float  # sample spread
    stderr: float  # uncertainty of the mean
    unit_value: float  # value of one full unit (copies × mean)
    adopted: bool  # False if spread exceeded tolerance
    note: str = ""


class NaturalStandard:
    """A measure defined as N copies of a natural reference object.

    name: e.g. "inch". reference_object: e.g. "barleycorn". copies: how
    many make one unit. base_unit: the unit the adopted value is
    expressed in (kept abstract — the caller's measuring unit).
    max_relative_spread: the quorum rule — the largest acceptable
    coefficient of variation before adoption is refused.
    """

    def __init__(
        self,
        name: str,
        reference_object: str,
        copies: int,
        base_unit: str = "unit",
        max_relative_spread: float = 0.10,
    ) -> None:
        if copies < 1:
            raise NaturalStandardError("copies must be >= 1")
        self.name = name
        self.reference_object = reference_object
        self.copies = copies
        self.base_unit = base_unit
        self.max_relative_spread = max_relative_spread
        self._adopted: Optional[Calibration] = None
        self.calibrations: List[Calibration] = []

    def calibrate(self, sample: List[float]) -> Calibration:
        """Derive the unit from a field sample of measured reference objects.

        sample: measured lengths of individual reference objects, in base
        units. The mean becomes the working reference length; adoption is
        refused (adopted=False) if relative spread exceeds the quorum.
        """
        if len(sample) < 2:
            raise NaturalStandardError("need at least 2 samples to calibrate")
        mean = statistics.fmean(sample)
        stdev = statistics.stdev(sample)
        stderr = stdev / math.sqrt(len(sample))
        rel_spread = stdev / mean if mean else math.inf
        adopted = rel_spread <= self.max_relative_spread
        cal = Calibration(
            sample_size=len(sample),
            mean=mean,
            stdev=stdev,
            stderr=stderr,
            unit_value=self.copies * mean,
            adopted=adopted,
            note=(
                f"{self.copies} {self.reference_object}s → 1 {self.name}"
                if adopted
                else f"refused: relative spread {rel_spread:.3f} > {self.max_relative_spread}"
            ),
        )
        self.calibrations.append(cal)
        if adopted:
            self._adopted = cal
        return cal

    @property
    def unit_value(self) -> float:
        """Adopted value of one unit, in base units."""
        if self._adopted is None:
            raise NaturalStandardError(f"{self.name!r} has no adopted calibration yet")
        return self._adopted.unit_value

    def audit(self, sample: List[float], tolerance: float) -> Tuple[bool, float]:
        """Re-check a fresh sample against the adopted unit.

        Returns (within_tolerance, deviation). The field-audit anyone can
        run: grow the reference, measure, compare.
        """
        cal = self._current_calibration_for_audit(sample)
        deviation = abs(cal.unit_value - self.unit_value)
        return (deviation <= tolerance, deviation)

    def _current_calibration_for_audit(self, sample: List[float]) -> Calibration:
        if len(sample) < 2:
            raise NaturalStandardError("need at least 2 samples to audit")
        mean = statistics.fmean(sample)
        stdev = statistics.stdev(sample) if len(sample) > 2 else 0.0
        stderr = stdev / math.sqrt(len(sample)) if len(sample) > 2 else 0.0
        return Calibration(
            sample_size=len(sample),
            mean=mean,
            stdev=stdev,
            stderr=stderr,
            unit_value=self.copies * mean,
            adopted=True,
            note="audit sample (not adopted)",
        )

    def grade(self, steps: int) -> List[Tuple[int, float]]:
        """Bootstrap stepped sizes — the shoe-size trick.

        Returns ``steps`` grades: grade k = k × unit_value. Grading from a
        self-replicating standard needs no second measure.
        """
        if steps < 1:
            raise NaturalStandardError("steps must be >= 1")
        value = self.unit_value  # raises if uncalibrated — honestly
        return [(k, k * value) for k in range(1, steps + 1)]
