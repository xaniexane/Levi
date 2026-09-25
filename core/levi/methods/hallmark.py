"""Hallmarks and Assay Offices: struck provenance.

Origin: Edward I's 1300 statute required silver offered for sale to
match the coin of the realm (92.5% sterling); Goldsmiths' wardens
assayed workshops and struck the leopard's-head mark on passing pieces
— substandard work was destroyed and the metal forfeited to the king.
The trust chain was tripartite and struck into the artifact: maker's
mark (who made it) + assay-office mark (independent tester) + fineness
+ date letter (which assay, when, and on whose watch). The radical move
was that the tester was also accountable: a fraudulent piece traced
back to the assayer's year. Maker claims and verification were
structurally separated.

What it is in LEVI: ``StruckProvenance`` — stamp an artifact with the
maker's claim, an independent assay result, and a timestamp.
``verify`` checks all three marks of the chain; a failed assay taints
the artifact, and exposed assay fraud taints the assayer's own record
too — the tester answers for the test.

Honesty label: LOAD-BEARING — tripartite struck provenance with
assayer accountability is a concrete, transferable mechanism.

Deny-closed inputs: empty maker / artifact / assayer / date fields,
fineness claims outside (0, 1], non-boolean assay outcomes, stamping an
artifact twice, verifying or reporting fraud on an unknown artifact,
and reporting fraud on an artifact whose assay already failed are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["StruckStamp", "StruckProvenance"]


@dataclass
class StruckStamp:
    """The three marks struck into one artifact: who claims to have made
    it, what the independent tester found, and when the test happened."""

    artifact_id: str
    maker: str
    fineness_claim: float
    assay_pass: bool
    assayer: str
    date: str
    fraudulent: bool = field(default=False, repr=False)


class StruckProvenance:
    """Tripartite provenance: maker claim + assay mark + date. The
    assayer is accountable — fraud traces back to the assayer's record."""

    def __init__(self):
        self._stamps: dict[str, StruckStamp] = {}
        self._assayer_strikes: dict[str, int] = {}

    def stamp(
        self,
        artifact_id: str,
        maker: str,
        fineness_claim: float,
        assay_pass: bool,
        assayer: str,
        date: str,
    ) -> StruckStamp:
        """Strike the three marks into an artifact's record."""
        for label, value in (
            ("artifact_id", artifact_id),
            ("maker", maker),
            ("assayer", assayer),
            ("date", date),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be a non-empty string")
        if (
            not isinstance(fineness_claim, (int, float))
            or isinstance(fineness_claim, bool)
            or not 0 < fineness_claim <= 1
        ):
            raise ValueError("fineness_claim must be within (0, 1]")
        if not isinstance(assay_pass, bool):
            raise ValueError("assay_pass must be a boolean")
        artifact_id = artifact_id.strip()
        if artifact_id in self._stamps:
            raise ValueError(f"artifact already stamped: {artifact_id!r}")
        stamp = StruckStamp(
            artifact_id=artifact_id,
            maker=maker.strip(),
            fineness_claim=float(fineness_claim),
            assay_pass=assay_pass,
            assayer=assayer.strip(),
            date=date.strip(),
        )
        self._stamps[artifact_id] = stamp
        self._assayer_strikes.setdefault(stamp.assayer, 0)
        return stamp

    def verify(self, artifact_id: str) -> dict:
        """Check the full chain: maker mark present, assay passed, date
        struck, and no fraud flagged. A failed assay is a failed verify —
        and the assayer's own record carries the taint."""
        stamp = self._stamps.get(artifact_id)
        if stamp is None:
            raise ValueError(f"unknown artifact: {artifact_id!r}")
        checks = {
            "maker_mark": bool(stamp.maker),
            "assay_passed": stamp.assay_pass and not stamp.fraudulent,
            "date_struck": bool(stamp.date),
            "fraud_flagged": stamp.fraudulent,
        }
        checks["verified"] = all(
            [checks["maker_mark"], checks["assay_passed"], checks["date_struck"]]
        )
        return checks

    def report_fraud(self, artifact_id: str, actual_fineness: float) -> dict:
        """Expose a passing assay as fraudulent: the piece tested below
        its claimed fineness. The artifact is flagged and the assayer's
        record takes a strike."""
        stamp = self._stamps.get(artifact_id)
        if stamp is None:
            raise ValueError(f"unknown artifact: {artifact_id!r}")
        if not stamp.assay_pass:
            raise ValueError(
                f"no fraud to report: {artifact_id!r} already failed assay"
            )
        if (
            not isinstance(actual_fineness, (int, float))
            or isinstance(actual_fineness, bool)
            or not 0 < actual_fineness <= 1
        ):
            raise ValueError("actual_fineness must be within (0, 1]")
        stamp.fraudulent = True
        self._assayer_strikes[stamp.assayer] += 1
        return {
            "artifact_id": artifact_id,
            "claimed": stamp.fineness_claim,
            "actual": float(actual_fineness),
            "assayer": stamp.assayer,
            "assayer_strikes": self._assayer_strikes[stamp.assayer],
        }

    def assayer_record(self, assayer: str) -> dict:
        """The assayer's own accountability record: strikes for fraud."""
        if not isinstance(assayer, str) or not assayer.strip():
            raise ValueError("assayer must be a non-empty string")
        assayer = assayer.strip()
        stamped = [s for s in self._stamps.values() if s.assayer == assayer]
        if not stamped:
            raise ValueError(f"unknown assayer: {assayer!r}")
        return {
            "assayer": assayer,
            "artifacts_tested": len(stamped),
            "fraud_strikes": self._assayer_strikes.get(assayer, 0),
        }
