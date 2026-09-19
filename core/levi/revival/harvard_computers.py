"""A human compute cluster: two-layer independent examination of sky plates.

Studied from: pre-digital-computation-20260916/report.md [Beat C #1]
(Harvard Observatory women computers, 1881-1950s)

The studied shape: photographic plates flow through a reduction line —
measure positions and brightness, classify by spectrum, then catalog —
and the discipline is two-layer independence: two computers examine
the same plate independently, and a second pass reconciles the results
before anything enters the catalog. The catalog carries provenance:
who measured, who checked, and where they disagreed.

LEVI-native re-expression: a **Plate** carries raw observations
(star ids with measured positions and magnitudes); an **Examiner**
runs a measurement pass (a heuristic reduction function, labeled as
such); **independent_examination** runs two examiners over the same
plate and reconciles them within a tolerance, flagging disagreements;
the **Catalog** stores only reconciled entries, each annotated with
both examiners and an agreement flag.

Operations:

* ``Plate(id, observations)`` — raw plate data: star_id -> (x, y, magnitude)
* ``Examiner(name, reducer)`` — one human's reduction pass; ``examine(plate)``
* ``independent_examination(plate, first, second, tolerance)`` — two passes + reconciliation
* ``Catalog.admit(examination)`` — store agreed entries with provenance

Honest limits: the reducers are caller-supplied heuristics (stand-ins
for human judgment), not simulations of astronomers. Agreement is a
numeric tolerance check on magnitude, not astrophysical validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/harvard-computers"

# A reducer is a heuristic stand-in for one human's measurement pass:
# plate_id -> star_id -> measured magnitude.
Reducer = Callable[[str, Dict[str, tuple]], Dict[str, float]]


@dataclass(frozen=True)
class Plate:
    """One raw plate: star_id -> (x, y, instrumental_magnitude)."""

    plate_id: str
    observations: Dict[str, tuple]

    def __post_init__(self) -> None:
        for star_id, obs in self.observations.items():
            if len(obs) != 3:
                raise ValueError(
                    f"observation for {star_id!r} must be (x, y, magnitude)"
                )


@dataclass
class Examination:
    """One examiner's independent pass over one plate."""

    plate_id: str
    examiner: str
    magnitudes: Dict[str, float]

    def stars(self) -> List[str]:
        return sorted(self.magnitudes)


@dataclass(frozen=True)
class ReconciledStar:
    """A star's agreed magnitude, or a flagged disagreement."""

    star_id: str
    plate_id: str
    magnitude: Optional[float]
    examiners: tuple
    agreed: bool
    spread: float


class Examiner:
    """One computer in the cluster, running her own reduction heuristic."""

    def __init__(self, name: str, reducer: Reducer) -> None:
        self.name = name
        self.reducer = reducer

    def examine(self, plate: Plate) -> Examination:
        magnitudes = self.reducer(plate.plate_id, plate.observations)
        return Examination(
            plate_id=plate.plate_id, examiner=self.name, magnitudes=magnitudes
        )


def independent_examination(
    plate: Plate,
    first: Examiner,
    second: Examiner,
    tolerance: float = 0.1,
) -> List[ReconciledStar]:
    """Run two independent passes and reconcile them.

    Stars where both passes agree within ``tolerance`` get the mean
    magnitude; larger spreads are flagged as disagreements and left out
    of the agreed value (magnitude=None).
    """
    run_a = first.examine(plate)
    run_b = second.examine(plate)
    stars = set(run_a.magnitudes) | set(run_b.magnitudes)
    reconciled: List[ReconciledStar] = []
    for star_id in sorted(stars):
        ma = run_a.magnitudes.get(star_id)
        mb = run_b.magnitudes.get(star_id)
        examiners = (run_a.examiner, run_b.examiner)
        if ma is None or mb is None:
            reconciled.append(
                ReconciledStar(
                    star_id, plate.plate_id, None, examiners, False, float("inf")
                )
            )
            continue
        spread = abs(ma - mb)
        agreed = spread <= tolerance
        reconciled.append(
            ReconciledStar(
                star_id=star_id,
                plate_id=plate.plate_id,
                magnitude=(ma + mb) / 2 if agreed else None,
                examiners=examiners,
                agreed=agreed,
                spread=spread,
            )
        )
    return reconciled


@dataclass
class CatalogEntry:
    """One admitted catalog line, with full examination provenance."""

    star_id: str
    plate_id: str
    magnitude: float
    examiners: tuple
    agreed: bool


class Catalog:
    """The catalog: only reconciled results, always with provenance."""

    def __init__(self) -> None:
        self.entries: List[CatalogEntry] = []
        self.disagreements: List[ReconciledStar] = []

    def admit(self, reconciled: List[ReconciledStar]) -> int:
        """Admit agreed stars; park disagreements for a third look. Returns admitted count."""
        admitted = 0
        for star in reconciled:
            if star.agreed and star.magnitude is not None:
                self.entries.append(
                    CatalogEntry(
                        star_id=star.star_id,
                        plate_id=star.plate_id,
                        magnitude=star.magnitude,
                        examiners=star.examiners,
                        agreed=True,
                    )
                )
                admitted += 1
            else:
                self.disagreements.append(star)
        return admitted

    def lookup(self, star_id: str) -> List[CatalogEntry]:
        return [e for e in self.entries if e.star_id == star_id]
