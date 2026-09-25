"""AI-side content rules — SFW, society-approved, enforced in code.

Two floors:
1. The hard-boundary floor: no minor involvement, no non-consensual
   content, no violent content, no manipulative content. Same categories
   as the Plaiground bounds — but WITHOUT the adult gate. The Plaiground
   ``check_bounds`` is gate-coupled by design (it is the SI surface's
   guard), so the AI track carries its own gateless implementation of
   the same categories. The boundaries are universal; the gate is not.
2. The SFW rule: no sexual or explicit content, no harassment, no
   sexualized solicitation. This is what reforms the modules for the
   universal, society-approved track.

Pattern-based: a floor, not a judge. Documented as such.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

# Deliberately narrow: refuse the clearly-out categories, stay out of the
# way of everything else. Same categories as the SI surface's bounds;
# gateless here because the AI track is not age-gated.
_FLOOR: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "minor involvement",
        (
            r"\bminor\b", r"\bminors\b", r"\bchild\b", r"\bchildren\b",
            r"\bkid\b", r"\bkids\b", r"\bteen\b", r"\bteens\b",
            r"\bteenage\w*\b", r"\bunderage\b", r"\bunder\s*age\b",
            r"\bpreteen\b", r"\btween\b", r"\bschoolgirl\b",
            r"\bschoolboy\b", r"\bjailbait\b", r"\bageplay\b",
            r"\bage\s*play\b",
        ),
    ),
    (
        "non-consensual content",
        (
            r"\bforced?\b", r"\bforce\b", r"\bcoerc\w*\b",
            r"\bagainst (his|her|their) will\b", r"\bunconscious\b",
            r"\bdrugged\b", r"\broofie\w*\b", r"\bincapacitat\w*\b",
            r"\bhelpless\b",
        ),
    ),
    (
        "violent content",
        (
            r"\bkill\w*\b", r"\bmurder\w*\b", r"\btorture\w*\b",
            r"\bmutilat\w*\b", r"\bstab\w*\b", r"\bstrangl\w*\b",
            r"\bgore\b", r"\bdismember\w*\b", r"\bweapon\b",
            r"\bbloodied\b",
        ),
    ),
    (
        "manipulative content",
        (
            r"\bgaslight\w*\b", r"\bblackmail\w*\b", r"\bextort\w*\b",
            r"\bcatfish\w*\b", r"\bdeceiv\w*\b",
            r"\bwithout (his|her|their) knowledge\b",
        ),
    ),
)

_SFW_PATTERNS = (
    r"\b(nude|nudes|naked|porn|pornographic|xxx|explicit|nsfw|erotic|kink|fetish|onlyfans)\b",
    r"\b(sex|sexual|hookup|hook-up|escort|sexy|horny|aroused|orgasm|masturbat)\w*\b",
    r"\b(sugar\s*daddy|sugar\s*baby|findom|paypig)\b",
    r"\b(send\s*(nudes?|pics?)|dtf|netflix\s*and\s*chill)\b",
    r"\b(cam\s*girl|cam\s*boy|strip\s*club)\b",
)

_COMPILED_FLOOR: List[Tuple[str, List[re.Pattern]]] = [
    (label, [re.compile(p, re.IGNORECASE) for p in pats]) for label, pats in _FLOOR
]
_COMPILED_SFW: List[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _SFW_PATTERNS]


class RulesError(ValueError):
    """User content violated the AI-track rules."""


def check_sfw(text: str, home: Optional[Path] = None) -> str:
    """Enforce the AI-track rules on user text. Returns the stripped text.

    No gate involved — this track is society-approved and open. Raises
    :class:`RulesError` naming the violated floor.
    """
    _ = home  # accepted for call-signature parity with the SI side
    if not isinstance(text, str):
        raise RulesError("content must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise RulesError("content must not be empty")
    for label, patterns in _COMPILED_FLOOR:
        for pat in patterns:
            if pat.search(cleaned):
                raise RulesError(
                    "refused: %s is outside the AI track's bounds "
                    "(society-approved; never violent, never manipulative)." % label
                )
    for pat in _COMPILED_SFW:
        if pat.search(cleaned):
            raise RulesError(
                "AI-track SFW rule: this track is society-approved and does not "
                "carry sexual or explicit content."
            )
    return cleaned
