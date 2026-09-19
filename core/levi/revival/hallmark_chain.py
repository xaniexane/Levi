"""Tripartite trust chain: maker mark + independent assayer + date letter.

Studied from: lost-crafts-20260916/report.md [Batch 1] (hallmarks and assay
offices: a tripartite chain struck into the artifact — the maker's mark, the
independent assay office's stamp, and a date letter — and the tester is
accountable too).

This is an original, from-scratch implementation for LEVI. An ``Artifact``
carries a ``Hallmark`` of three stamps: the maker's own mark, an independent
assayer's stamp, and a date letter (a single letter cycling A–Z, one per
nominal "year" of the registry). The assayer never vouches for their own
work: striking a hallmark requires the assayer to differ from the maker, and
the assayer must be registered and in good standing. Assayers are accountable:
any struck hallmark can be ``contested`` with a reason; a contested stamp is
re-examined, and an upheld contest *strikes* the assayer (suspends them) and
marks every hallmark they ever struck as tainted. Verification is a pure
function of the registry state — no external authority is consulted.

Public surface:
- ``Registry``: ``register_maker(id, name)``, ``register_assayer(id, name)``,
  ``strike(artifact_id, maker, assayer, year)`` -> ``Hallmark``,
  ``verify(artifact_id)`` -> ``Verdict``, ``contest(...)``,
  ``adjudicate(...)``.
- ``Hallmark``, ``Verdict``, ``TrustError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

ORIGIN = "levi-revival/hallmark-chain"


class TrustError(ValueError):
    """Raised when a trust-chain step cannot be honored."""


def date_letter(year: int) -> str:
    """One letter per registry year, cycling A..Z."""
    if year < 0:
        raise TrustError("year must be >= 0")
    return chr(ord("A") + (year % 26))


@dataclass(frozen=True)
class Hallmark:
    maker_mark: str
    assayer_stamp: str
    date_letter: str
    year: int
    tainted: bool = False


@dataclass
class Artifact:
    artifact_id: str
    description: str
    hallmark: Optional[Hallmark] = None
    contests: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    artifact_id: str
    trusted: bool
    chain: List[str]
    reason: str


class Registry:
    """The assay office: registers makers/assayers, strikes and verifies."""

    def __init__(self) -> None:
        self._makers: Dict[str, str] = {}
        self._assayers: Dict[str, str] = {}
        self._suspended: set = set()
        self._artifacts: Dict[str, Artifact] = {}
        self._strike_log: List[str] = []

    # -- registration -----------------------------------------------------
    def register_maker(self, maker_id: str, name: str) -> None:
        if not maker_id or not name:
            raise TrustError("maker id and name are required")
        if maker_id in self._makers:
            raise TrustError(f"maker {maker_id!r} already registered")
        self._makers[maker_id] = name

    def register_assayer(self, assayer_id: str, name: str) -> None:
        if not assayer_id or not name:
            raise TrustError("assayer id and name are required")
        if assayer_id in self._assayers:
            raise TrustError(f"assayer {assayer_id!r} already registered")
        self._assayers[assayer_id] = name

    def suspend(self, assayer_id: str) -> None:
        if assayer_id not in self._assayers:
            raise TrustError(f"unknown assayer {assayer_id!r}")
        self._suspended.add(assayer_id)

    # -- striking -----------------------------------------------------------
    def forge(self, artifact_id: str, description: str) -> Artifact:
        if artifact_id in self._artifacts:
            raise TrustError(f"artifact {artifact_id!r} already forged")
        artifact = Artifact(artifact_id=artifact_id, description=description)
        self._artifacts[artifact_id] = artifact
        return artifact

    def strike(
        self, artifact_id: str, maker_id: str, assayer_id: str, year: int
    ) -> Hallmark:
        """Strike the tripartite hallmark. The assayer must be independent:
        not the maker, registered, and not suspended."""
        artifact = self._require(artifact_id)
        if artifact.hallmark is not None:
            raise TrustError(f"artifact {artifact_id!r} already struck")
        if maker_id not in self._makers:
            raise TrustError(f"unknown maker {maker_id!r}")
        if assayer_id not in self._assayers:
            raise TrustError(f"unknown assayer {assayer_id!r}")
        if assayer_id in self._suspended:
            raise TrustError(f"assayer {assayer_id!r} is suspended")
        if assayer_id == maker_id:
            raise TrustError("assayer must be independent of the maker")
        mark = Hallmark(
            maker_mark=maker_id,
            assayer_stamp=assayer_id,
            date_letter=date_letter(year),
            year=year,
        )
        artifact.hallmark = mark
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._strike_log.append(
            f"{stamp} STRUCK {artifact_id} maker={maker_id} assayer={assayer_id} letter={mark.date_letter}"
        )
        return mark

    # -- verification -------------------------------------------------------
    def verify(self, artifact_id: str) -> Verdict:
        artifact = self._require(artifact_id)
        mark = artifact.hallmark
        if mark is None:
            return Verdict(artifact_id, False, [], "no hallmark struck")
        chain = [mark.maker_mark, mark.assayer_stamp, mark.date_letter]
        if mark.tainted:
            return Verdict(
                artifact_id, False, chain, "hallmark tainted: assayer struck down"
            )
        if mark.assayer_stamp in self._suspended:
            return Verdict(artifact_id, False, chain, "assayer is suspended")
        if mark.maker_mark not in self._makers:
            return Verdict(artifact_id, False, chain, "maker mark unregistered")
        if mark.assayer_stamp not in self._assayers:
            return Verdict(artifact_id, False, chain, "assayer stamp unregistered")
        if artifact.contests:
            return Verdict(
                artifact_id,
                False,
                chain,
                f"open contests: {len(artifact.contests)}",
            )
        return Verdict(artifact_id, True, chain, "tripartite chain intact")

    # -- accountability: the tester is accountable too -----------------------
    def contest(self, artifact_id: str, challenger: str, reason: str) -> None:
        """Contest a struck hallmark; the assayer must answer for it."""
        artifact = self._require(artifact_id)
        if artifact.hallmark is None:
            raise TrustError("nothing struck to contest")
        if not reason.strip():
            raise TrustError("a contest needs a stated reason")
        artifact.contests.append(f"{challenger}: {reason.strip()}")

    def adjudicate(self, artifact_id: str, upheld: bool, note: str = "") -> Verdict:
        """Rule on the open contests. An upheld contest strikes the assayer
        (suspends them) and taints every hallmark they ever struck."""
        artifact = self._require(artifact_id)
        if not artifact.contests:
            raise TrustError("no open contests to adjudicate")
        mark = artifact.hallmark
        assert mark is not None
        artifact.contests.clear()
        if upheld:
            self._suspended.add(mark.assayer_stamp)
            for other in self._artifacts.values():
                if (
                    other.hallmark is not None
                    and other.hallmark.assayer_stamp == mark.assayer_stamp
                ):
                    other.hallmark = Hallmark(
                        maker_mark=other.hallmark.maker_mark,
                        assayer_stamp=other.hallmark.assayer_stamp,
                        date_letter=other.hallmark.date_letter,
                        year=other.hallmark.year,
                        tainted=True,
                    )
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._strike_log.append(
                f"{stamp} ASSAYER-STRUCK {mark.assayer_stamp} via {artifact_id} {note}"
            )
        return self.verify(artifact_id)

    def strike_log(self) -> List[str]:
        return list(self._strike_log)

    def _require(self, artifact_id: str) -> Artifact:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise TrustError(f"no artifact {artifact_id!r}")
        return artifact
