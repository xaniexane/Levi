"""Native SI core for Alpha — first mind, reasoning."""

from __future__ import annotations

from levi.si_team.si.core import SiCore


def _pros_cons(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "ALPHA — reasoning by structure. Break the question into three: "
        "premises (what must be true), options (what could be done), "
        "trade-offs (what each option costs). I work the structure, I do "
        "not invent facts — every inference stays marked as inference."
    )


def _explain(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "ALPHA — reasoning step by step. First: what is actually being "
        "asked? Second: what do we know for certain? Third: what follows "
        "from that alone? If the task gives me premises I don't have, I "
        "say so plainly instead of filling the gap with confidence."
    )


def _compare(task: str, tokens: list) -> str:  # noqa: ARG001
    return (
        "ALPHA — comparing two options. Line them up on the same axes: "
        "cost, effort, reversibility, and fit with the binding laws. The "
        "option that wins on the most axes with the fewest hidden costs "
        "is the reasoning's answer — but the verdict belongs to Omega."
    )


class AlphaCore(SiCore):
    role = "alpha"
    corpus_note_text = (
        "Corpus note: Alpha's reasoning corpus is LEVI's own archive of "
        "analyses, trade-off write-ups, and harvested learnings. The "
        "dedicated Alpha substrate (levi.alpha) is being built separately; "
        "until it lands, the rules engine reasons here."
    )
    rules = [
        (("pros", "cons"), _pros_cons),
        (("trade", "off"), _pros_cons),
        (("explain",), _explain),
        (("why",), _explain),
        (("how",), _explain),
        (("compare", "versus", "vs"), _compare),
        (("which", "better"), _compare),
    ]
