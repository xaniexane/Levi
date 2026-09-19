"""SICI — SI-class (synthetic) Cloud Intelligence.

Dynasty-native counsel for the SI-class minions: the rows carrying the
keeper's full Wave-B signature. SICI reasons the way its class was built —
traversing the organs in deliberation:

  echo      — reflect the case back; surface taken / not-taken / wild
              branches of the advice
  mandella  — stake the alternatives under pressure; let the phantoms
              (the advices not chosen) haunt the verdict honestly
  reim      — compost the failed proposals: what did the losing takes
              get right?
  riem      — compress the retained signal into the verdict: zip, not burn

These are named deliberation phases of one local counsel — honest about
what they are, never a claim of separate minds.
"""

from __future__ import annotations

from typing import List

from levi.ci.counsel import Case, Challenge, CloudCounsel, Proposal, Seat, Verdict

_ORGANS = ("echo", "mandella", "reim", "riem")


class SICI(CloudCounsel):
    name = "SICI"
    class_tag = "SI"
    character = "synthetic/dynasty-native reasoning"

    def propose(self, case: Case) -> List[Proposal]:
        proposals = super().propose(case)
        # The echo phase: each proposal carries its reflected branches.
        echoed: List[Proposal] = []
        for prop in proposals:
            echoed.append(
                Proposal(
                    seat_id=prop.seat_id,
                    ruling=prop.ruling,
                    rationale=(
                        f"[echo] {prop.rationale} branches: taken={prop.ruling}; "
                        f"not-taken={[r for r in ('proceed','proceed-with-conditions','hold-for-human','refuse') if r != prop.ruling][:2]}; "
                        f"wild=the case the minion was never built for."
                    ),
                )
            )
        return echoed

    def _seat_rationale(self, seat: Seat, case: Case) -> str:
        return (
            f"SICI {seat.role} {seat.seat_id} reasons natively: "
            f"stakes={case.stakes}, question='{case.question}'."
        )

    def _challenge_objection(
        self, challenger: Seat, proposal: Proposal, case: Case
    ) -> str:
        return (
            f"SICI {challenger.seat_id} [mandella] stakes {proposal.seat_id}'s "
            f"'{proposal.ruling}': under domain pressure it holds, but the "
            f"phantom — the advice not chosen — haunts it. "
            f"[reim] the losing take composts into: what did it get right?"
        )

    def arbitrate(
        self, case: Case, proposals: List[Proposal], challenges: List[Challenge]
    ) -> Verdict:
        verdict = super().arbitrate(case, proposals, challenges)
        # The RIEM phase: compress the retained signal into the verdict.
        verdict.rationale = (
            f"[riem] retained signal zipped into verdict: {verdict.rationale}"
        )
        verdict.substrate["deliberation_organs"] = list(_ORGANS)
        return verdict


def counsel() -> SICI:
    return SICI()
