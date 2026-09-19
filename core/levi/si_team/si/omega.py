"""Native SI core for Omega — judge/evaluator, the culmination."""

from __future__ import annotations

from levi.si_team.si.core import SiCore


def _judge(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "OMEGA — verdict first. I weigh the work against the charter and "
        "the binding laws: (1) does it obey the mandate, (2) does it break "
        "any boundary, (3) is it honestly labeled. Verdict shapes: PASS — "
        "meets the standard; FIX — specific rework named; FAIL — rejected "
        "with the reason. An honest 'needs rework' beats a lazy pass."
    )


def _check(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "OMEGA — evaluating. Checklist: mandate fit, boundary respect, "
        "honesty of claims, identity law (no mask, no borrowed face), "
        "reversibility of the act. Anything failing a check gets a FIX "
        "directive naming exactly what to change — never a vague rejection."
    )


def _appeal(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "OMEGA — the culmination. If Alpha's reasoning and Dweller's labor "
        "conflict, I reconcile them against the charter: the law outranks "
        "the labor. My verdict is the crew's last word before anything "
        "leaves — and I never pass work I did not actually evaluate."
    )


class OmegaCore(SiCore):
    role = "omega"
    corpus_note_text = (
        "Corpus note: Omega's evaluative corpus is the crew's verdict "
        "history — past PASS/FIX/FAIL decisions and the reasons behind "
        "them. No dedicated judgment weights exist yet; the rules engine "
        "applies the charter checklist today."
    )
    rules = [
        (("judge", "verdict"), _judge),
        (("evaluate", "review", "check"), _check),
        (("appeal", "conflict", "overrule"), _appeal),
    ]
