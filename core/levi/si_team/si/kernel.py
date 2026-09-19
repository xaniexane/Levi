"""SI Team rules engine — shared deterministic kernel for the native SI cores.

stdlib only. No network, no weights, no side effects. Each role core owns
its own rule set over this kernel; the kernel scores keyword matches and
returns the best-matching response.
"""

from __future__ import annotations

import re
from typing import Callable, List, Sequence, Tuple

_WORD = re.compile(r"[a-z0-9]+")

Rule = Tuple[Sequence[str], Callable[[str, List[str]], str]]


def tokenize(task: str) -> List[str]:
    return _WORD.findall((task or "").lower())


def score(keywords: Sequence[str], tokens: List[str]) -> float:
    """Fraction of keyword tokens present in the task (0.0 when no keywords)."""
    if not keywords:
        return 0.0
    hits = sum(1 for k in keywords if k in tokens)
    return hits / len(keywords)


def reason(
    rules: Sequence[Rule], task: str, fallback: Callable[[str], str]
) -> Tuple[str, str]:
    """Pick the best rule for *task* and build the answer.

    Returns (answer, rule_tag). The tag is the matched rule's keyword line
    or 'fallback' — always honest about what fired.
    """
    tokens = tokenize(task)
    best: Rule | None = None
    best_score = 0.0
    for rule in rules:
        s = score(rule[0], tokens)
        if s > best_score:
            best, best_score = rule, s
    if best is None or best_score <= 0.0:
        return fallback(task), "fallback"
    tag = "+".join(best[0])
    return best[1](task, tokens), tag
