"""capability_strings — short scriptable strings as capability policy.

Studied from: dead-networks-20260916/report.md (Renegade BBS: ACS,
access-control strings — 's10g5'-style strings controlling menus,
security levels and display, evaluated locally).

The load-bearing idea: capability policy as a terse, human-writable
string — a letter names a capability, a following number grades it.
No database lookup, no remote call: the string is parsed locally and
evaluated against the live session. Policy travels as text.

LEVI's take: ``parse_acs("s10g5m")`` yields a ``CapabilitySet`` of
(letter, level) claims. ``allows`` evaluates claims against a
context dict (``security``, ``group``, ``time_left_s``, ...):
``s10`` demands security >= 10, ``g5`` group membership, ``t30``
at least 30s left, ``m``/``d``/``f`` are named boolean features.
Compound strings AND their claims; ``describe`` renders the policy
in plain words. This is an original, from-scratch implementation
for LEVI.

Honest limits: a tiny policy language, not a full ACL engine — no
negation, no OR, no delegation. Unknown letters are rejected at
parse time rather than ignored. Levels are integers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/capability-strings"

# letter -> (human name, kind, context key)
# kind "level": claim passes when context[key] >= number
# kind "flag":  claim passes when number != 0 (bare letter means 1)
# kind "member": claim passes when number is in context[key] (a set)
_CAPS: Dict[str, Tuple[str, str, str]] = {
    "s": ("security level", "level", "security"),
    "g": ("group", "member", "groups"),
    "t": ("minutes remaining", "level", "minutes_left"),
    "m": ("menu access", "flag", "menu_ok"),
    "d": ("display extras", "flag", "display_ok"),
    "f": ("file area", "flag", "files_ok"),
    "c": ("chat", "flag", "chat_ok"),
    "x": ("external programs", "flag", "doors_ok"),
}

_TOKEN = re.compile(r"([a-zA-Z])(\d*)")


@dataclass(frozen=True)
class Claim:
    """One parsed (letter, level) claim."""

    letter: str
    level: int

    @property
    def name(self) -> str:
        return _CAPS[self.letter][0]


@dataclass(frozen=True)
class CapabilitySet:
    """A parsed ACS string, ready to evaluate."""

    claims: tuple
    source: str

    def allows(self, context: Dict[str, object]) -> bool:
        """True when EVERY claim is satisfied by ``context``."""
        return all(_satisfied(claim, context) for claim in self.claims)

    def failing(self, context: Dict[str, object]) -> List[Claim]:
        """The claims that ``context`` does NOT satisfy."""
        return [c for c in self.claims if not _satisfied(c, context)]

    def describe(self) -> List[str]:
        return [_describe(claim) for claim in self.claims]


def _satisfied(claim: Claim, context: Dict[str, object]) -> bool:
    kind, key = _CAPS[claim.letter][1], _CAPS[claim.letter][2]
    value = context.get(key)
    if kind == "level":
        return isinstance(value, (int, float)) and value >= claim.level
    if kind == "flag":
        return bool(value) if claim.level else not bool(value)
    # kind == "member"
    return isinstance(value, (set, frozenset, list, tuple)) and claim.level in value


def _describe(claim: Claim) -> str:
    kind = _CAPS[claim.letter][1]
    name = _CAPS[claim.letter][0]
    if kind == "level":
        return f"requires {name} >= {claim.level}"
    if kind == "flag":
        return f"{'grants' if claim.level else 'denies'} {name}"
    return f"requires membership in group {claim.level}"


def parse_acs(source: str) -> CapabilitySet:
    """Parse an access-control string like ``"s10g5m"``.

    Raises ValueError on empty input, unknown letters, or stray
    characters — policy never fails open.
    """
    text = source.strip().lower()
    if not text:
        raise ValueError("ACS string must be non-empty")
    claims: List[Claim] = []
    pos = 0
    for match in _TOKEN.finditer(text):
        if match.start() != pos:
            raise ValueError(f"bad ACS syntax at {text[pos:]!r}")
        letter, digits = match.group(1), match.group(2)
        if letter not in _CAPS:
            raise ValueError(f"unknown capability letter {letter!r}")
        claims.append(Claim(letter, int(digits) if digits else 1))
        pos = match.end()
    if pos != len(text):
        raise ValueError(f"bad ACS syntax at {text[pos:]!r}")
    return CapabilitySet(claims=tuple(claims), source=text)


def demo() -> dict:
    """Parse 's10g5m', evaluate a qualifying and a failing session."""
    caps = parse_acs("s10g5m")
    good = {"security": 12, "groups": {5, 7}, "menu_ok": True}
    bad = {"security": 8, "groups": {5}, "menu_ok": True}
    return {
        "source": caps.source,
        "describe": caps.describe(),
        "good_session_allows": caps.allows(good),
        "bad_session_allows": caps.allows(bad),
        "bad_session_failing": [c.letter for c in caps.failing(bad)],
    }
