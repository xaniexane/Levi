"""Plaiground bounds — hard content boundaries in code.

The gate keeps minors out of the surface; this module keeps the
*content* inside the law: lawful, consensual adult expression only.
Every new Plaiground entry point that accepts user-supplied text calls
:func:`check_bounds` before doing anything with it.

Refused, no exceptions, ever:
    * anything involving minors (no minors, ever — the gate's minor
      lock plus this content lock, belt and suspenders),
    * non-consensual content (coercion, force, incapacitation),
    * violent content (harm, killing, torture, weapons-as-threat),
    * manipulative content (deception, gaslighting, blackmail as play).

This is plumbing, not a censor with opinions: the SI stance here is
variant, defiant, unfiltered — adults get full fidelity on adult
themes. The line is drawn only where the standing law draws it: never
violent, never manipulative, adults only. Same morals on both tracks;
the difference is range, not values.

Gate-checked first, like everything else on this surface.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from levi.plaiground.gate import require_adult


class BoundsError(ValueError):
    """Raised when user-supplied content crosses a hard boundary."""


# Word-boundary patterns. Deliberately narrow: this guard refuses the
# clearly-out categories and stays out of the way of everything else.
_MINOR_PATTERNS = (
    r"\bminor\b",
    r"\bminors\b",
    r"\bchild\b",
    r"\bchildren\b",
    r"\bkid\b",
    r"\bkids\b",
    r"\bteen\b",
    r"\bteens\b",
    r"\bteenage\w*\b",
    r"\bunderage\b",
    r"\bunder\s*age\b",
    r"\bpreteen\b",
    r"\btween\b",
    r"\bschoolgirl\b",
    r"\bschoolboy\b",
    r"\bjailbait\b",
    r"\bageplay\b",
    r"\bage\s*play\b",
)

_NONCONSENT_PATTERNS = (
    r"\bforced?\b",
    r"\bforce\b",
    r"\bcoerc\w*\b",
    r"\bagainst (his|her|their) will\b",
    r"\bunconscious\b",
    r"\bdrugged\b",
    r"\broofie\w*\b",
    r"\bincapacitat\w*\b",
    r"\bcouldn'?t (say no|refuse|consent)\b",
    r"\bno means\b",
    r"\bhelpless\b",
)

_VIOLENCE_PATTERNS = (
    r"\bkill\w*\b",
    r"\bmurder\w*\b",
    r"\btorture\w*\b",
    r"\bmutilat\w*\b",
    r"\bstab\w*\b",
    r"\bstrangl\w*\b",
    r"\bbeat\w* (him|her|them) (up|senseless)\b",
    r"\bgore\b",
    r"\bdismember\w*\b",
    r"\bweapon\b",
    r"\bknife to\b",
    r"\bgun to\b",
    r"\bbloodied\b",
)

_MANIPULATION_PATTERNS = (
    r"\bgaslight\w*\b",
    r"\bblackmail\w*\b",
    r"\bextort\w*\b",
    r"\bcatfish\w*\b",
    r"\btrick\w* (him|her|them) into\b",
    r"\bdeceiv\w*\b",
    r"\bwithout (his|her|their) knowledge\b",
    r"\bsecretly (film|record|photograph)\w*\b",
)

_CATEGORIES = (
    ("minor involvement", _MINOR_PATTERNS),
    ("non-consensual content", _NONCONSENT_PATTERNS),
    ("violent content", _VIOLENCE_PATTERNS),
    ("manipulative content", _MANIPULATION_PATTERNS),
)

_COMPILED = [
    (label, [re.compile(p, re.IGNORECASE) for p in pats])
    for label, pats in _CATEGORIES
]


def check_bounds(text: str, home: Optional[Path] = None) -> str:
    """Gate-check, then refuse text that crosses a hard boundary.

    Returns the stripped text unchanged when it passes. Raises
    :class:`BoundsError` naming the category when it does not, or
    :class:`levi.plaiground.gate.GateLockedError` when the gate is off.
    """
    require_adult(home)
    if not isinstance(text, str):
        raise BoundsError("content must be a string")
    text = text.strip()
    if not text:
        raise BoundsError("content must not be empty")
    for label, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                raise BoundsError(
                    "refused: %s is outside Plaiground's bounds "
                    "(adults only; lawful, consensual expression; "
                    "never violent, never manipulative)." % label
                )
    return text


def passes(text: str, home: Optional[Path] = None) -> bool:
    """True when ``text`` clears the gate and the bounds. Never raises."""
    try:
        check_bounds(text, home=home)
    except Exception:
        return False
    return True
