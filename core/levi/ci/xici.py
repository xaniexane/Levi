"""XICI — XI-class (nano-bit) Cloud Intelligence.

Nano-fast counsel for the XI-class minions: the trivial-turn bulk
(light-gate routine automations). Trivial cases deserve fast judgment, not
slow ceremony — so XICI deliberates on a fast path:

  - quorum of 1: a single seat can render the verdict
  - the challenge round is abbreviated to one press per proposal
  - repeated identical cases hit a verdict cache (same case fingerprint
    → same verdict), because a trivial turn judged twice should judge
    the same both times

Fast never means careless: anything above routine stakes, or any case the
fast path cannot settle, escalates out of the nano tier to AICI instead of
guessing. The counsel says when it stands down.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from levi.ci import aici
from levi.ci.counsel import Case, Challenge, CloudCounsel, Proposal, Seat, Verdict


class XICI(CloudCounsel):
    name = "XICI"
    class_tag = "XI"
    character = "nano-fast trivial-turn counsel"
    quorum = 1

    def __init__(self, n_seats: Optional[int] = 1):
        super().__init__(n_seats=n_seats if n_seats is not None else 1)
        self._verdict_cache: Dict[str, Verdict] = {}

    def _seat_ruling(self, seat: Seat, case: Case) -> str:
        # The nano tier never guesses at elevated stakes — it stands down.
        if case.stakes in ("elevated", "critical"):
            return "hold-for-human"
        return "proceed"

    def _seat_rationale(self, seat: Seat, case: Case) -> str:
        return (
            f"XICI {seat.seat_id} fast-path: trivial turn, stakes={case.stakes}, "
            f"question='{case.question}'. Judged at nano cost."
        )

    def challenge_round(self, case: Case, proposals: List[Proposal]) -> List[Challenge]:
        # Abbreviated: one press, self-challenge on the single proposal.
        if not proposals:
            return []
        prop = proposals[0]
        return [
            Challenge(
                challenger_id=prop.seat_id,
                target_seat_id=prop.seat_id,
                objection=(
                    f"XICI {prop.seat_id} self-press: is '{case.question}' truly "
                    f"trivial for {case.minion_id}? If not, this case leaves "
                    f"the nano tier."
                ),
            )
        ]

    def deliberate(self, case: Case) -> Verdict:
        fp = case.fingerprint()
        cached = self._verdict_cache.get(fp)
        if cached is not None:
            return cached
        if case.stakes in ("elevated", "critical"):
            verdict = self._escalate_out(case)
        else:
            verdict = super().deliberate(case)
        self._verdict_cache[fp] = verdict
        return verdict

    def _escalate_out(self, case: Case) -> Verdict:
        """Above routine stakes the nano tier stands down to AICI."""
        generalist = aici.AICI()
        verdict = generalist.deliberate(case)
        verdict.rationale = (
            f"XICI stood down (stakes={case.stakes} exceed the nano tier); "
            f"AICI rendered: {verdict.rationale}"
        )
        verdict.substrate["stood_down_from"] = "XICI"
        return verdict


def counsel() -> XICI:
    return XICI()
