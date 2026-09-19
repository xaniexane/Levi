"""AICI — AI-class Cloud Intelligence.

Generalist advisory counsel for the AI-class minions: the judgment-grade
gate carriers (dialog, approval, edit-approve, confirm). AICI weighs risk,
compares options, and hunts blind spots — the generalist judge the
operator consults before consequential turns.
"""

from __future__ import annotations

from typing import List

from levi.ci.counsel import Case, Challenge, CloudCounsel, Proposal, Seat


class AICI(CloudCounsel):
    name = "AICI"
    class_tag = "AI"
    character = "generalist advisory"

    def _seat_rationale(self, seat: Seat, case: Case) -> str:
        lens = {
            "proponent": "weighs the options and their consequences",
            "challenger": "hunts the blind spot in the favored option",
            "arbiter": "judges which advice survives contact with the worst case",
        }.get(seat.role, "advises")
        return (
            f"AICI {seat.role} {seat.seat_id} {lens}: stakes={case.stakes}, "
            f"question='{case.question}'."
        )

    def _challenge_objection(
        self, challenger: Seat, proposal: Proposal, case: Case
    ) -> str:
        return (
            f"AICI {challenger.seat_id} challenges {proposal.seat_id}: "
            f"the generalist view misses something — name the second-order "
            f"effect of '{proposal.ruling}' on {case.minion_id} before it stands."
        )


def counsel() -> AICI:
    return AICI()
