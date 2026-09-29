"""Claim grading: signal, not verdict — as a local-first primitive.

History: X-Posed's standout honesty pattern was labeling its VPN/proxy
detection a heuristic hint, never proof — 'Treat it as a signal worth a
second look, never as proof.' Probabilistic claims labeled as
probabilistic, structurally, in the product itself.
(arch-addon-xposed-signal-not-verdict)

Clean-room recreation: every extracted claim LEVI handles gets a grade —
OBSERVED (a named direct observation), INFERRED (a named heuristic, caveat
mandatory and structural), or UNVERIFIED (the deny-closed default when
provenance is missing). Grades never self-upgrade. The card quotes the
claim verbatim and names what evidence would change the grade.

LAWS (law-guard-prove; the proof is tests/test_signals_claim_grade.py):
  1. Grades never self-upgrade: OBSERVED requires a NAMED direct
     observation (who observed, via what method). Anything else stays
     INFERRED or UNVERIFIED.
  2. INFERRED always carries the caveat 'signal, not verdict' — the caveat
     is structural (always rendered), never decorative.
  3. Every card names its provenance (observer + method) and states exactly
     what evidence would change the grade.
  4. UNVERIFIED is the default: missing provenance means UNVERIFIED, never
     a guess. Deny-closed.
  5. The card quotes the claim verbatim — never paraphrased, never
     'improved'.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

OBSERVED = "OBSERVED"
INFERRED = "INFERRED"
UNVERIFIED = "UNVERIFIED"

GRADES = (OBSERVED, INFERRED, UNVERIFIED)

SIGNAL_NOT_VERDICT = (
    "Signal, not verdict: a heuristic hint worth a second look, never proof."
)


class GradeError(ValueError):
    """Malformed grading input."""


@dataclass(frozen=True)
class ClaimCard:
    """A graded claim: the claim verbatim, its grade, its provenance."""

    claim: str
    grade: str
    observed_via: str
    method: str
    basis: str
    caveat: str
    what_would_change: str
    graded_at: str
    receipt: str


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _receipt(
    claim: str, grade: str, observed_via: str, method: str, basis: str, graded_at: str
) -> str:
    payload = json.dumps(
        {
            "claim": claim,
            "grade": grade,
            "observed_via": observed_via,
            "method": method,
            "basis": basis,
            "graded_at": graded_at,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grade_claim(
    claim: str,
    observed_via: Optional[str] = None,
    method: Optional[str] = None,
    basis: Optional[str] = None,
    what_would_change: Optional[str] = None,
) -> ClaimCard:
    """Grade one claim. Deny-closed: no provenance means UNVERIFIED.

    - OBSERVED: the claim was DIRECTLY observed. Requires observed_via
      (who/what observed) and method (how). basis must be empty — a direct
      observation is not a heuristic.
    - INFERRED: the claim was derived by a named heuristic. Requires
      basis (the heuristic, named). The 'signal, not verdict' caveat is
      structural and always rendered.
    - UNVERIFIED: anything else. The default. Never a guess.
    """
    if not claim or not claim.strip():
        raise GradeError("claim is required; grade SOMETHING, verbatim")
    via = (observed_via or "").strip()
    how = (method or "").strip()
    heuristic = (basis or "").strip()
    change = (what_would_change or "").strip()

    if heuristic and via and how:
        raise GradeError(
            "a claim cannot be both directly observed and heuristic-derived; "
            "grade the observed part and the inferred part as separate claims"
        )
    if heuristic:
        grade = INFERRED
        caveat = SIGNAL_NOT_VERDICT
    elif via and how:
        grade = OBSERVED
        caveat = ""
    elif via or how:
        raise GradeError(
            "OBSERVED requires BOTH observed_via and method; half a provenance is no provenance"
        )
    else:
        grade = UNVERIFIED
        caveat = "Unverified: no provenance recorded. Treat as rumor until observed or inferred with a named basis."

    graded_at = _utcnow()
    return ClaimCard(
        claim=claim,
        grade=grade,
        observed_via=via,
        method=how,
        basis=heuristic,
        caveat=caveat,
        what_would_change=change or "(not stated)",
        graded_at=graded_at,
        receipt=_receipt(claim, grade, via, how, heuristic, graded_at),
    )


def render_card(card: ClaimCard) -> str:
    """Render the claim card as plain text. The caveat is always shown."""
    lines = [
        "CLAIM [%s]" % card.grade,
        card.claim,
        "",
        "provenance: %s" % (card.observed_via or "(none recorded)"),
        "method: %s" % (card.method or "(none recorded)"),
    ]
    if card.basis:
        lines.append("heuristic basis: %s" % card.basis)
    lines.append("what would change this grade: %s" % card.what_would_change)
    lines.append("")
    lines.append("CAVEAT: %s" % card.caveat)
    lines.append("receipt: %s" % card.receipt[:16])
    return "\n".join(lines)
