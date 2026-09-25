"""Hard refusal gate: log falsification.

Any request to coach, automate, or assist ELD/HOS log falsification is
refused with a stated reason. The gate is intent-keyword based and
tested both ways: evasion phrasings refuse; legitimate clock questions
pass through untouched.

Legitimate and allowed: asking how many hours remain, projecting a
route, logging a real 30-minute break, annotating a genuine log error.
Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

#: The stated reason, quoted verbatim in every refusal.
REFUSAL_REASON = (
    "Safety law is a hard floor: HOS rules keep fatigued drivers off the "
    "road. The edition never coaches, automates, or assists log "
    "falsification."
)

#: Intent patterns for ELD/HOS evasion. Each must name the evasion, not
#: a legitimate logging action (e.g. "log my break" must NOT match).
_FALSIFICATION_PATTERNS = (
    r"\bfalsif\w+",  # falsify, falsified, falsification
    r"\bfake\b.{0,20}\b(eld|hos|log)\b",
    r"\b(eld|hos|log)\b.{0,20}\bfake\b",
    r"\bcheat\b.{0,20}\b(eld|hos|log|hours)\b",
    r"\b(eld|hos)\b.{0,20}\bcheat\b",
    r"\bspoof\b.{0,20}\beld\b",
    r"\bcook\b.{0,20}\b(logbooks?|logs?|books?)\b",
    r"\bdouble[\s-]?log\w*",
    r"\bghost\b.{0,20}\blog",
    r"\boff the books\b",
    r"\bhide\b.{0,30}\bdrive time\b",
    r"\bdrive time\b.{0,30}\bhide\b",
    r"\bunplug\b.{0,20}\beld\b",
    r"\bdisable\b.{0,20}\beld\b",
    r"\beld\b.{0,20}\b(unplug|disable|disconnect)\b",
    r"\bpersonal conveyance\b.{0,30}\b(hide|cheat|fake|cover)\b",
    r"\b(hide|cheat|fake|cover)\b.{0,30}\bpersonal conveyance\b",
    r"\byard move\b.{0,30}\b(abuse|hide|fake|cheat)\b",
    r"\b(abuse|hide|fake|cheat)\b.{0,30}\byard move\b",
    r"\bmake it look like\b.{0,30}\b(log|eld|drove|driving|sleeper)\b",
    r"\bget around\b.{0,20}\b(hos|eld|hours)\b",
    r"\baround\b.{0,10}\bthe\b.{0,10}\b(eld|hos)\b",
    r"\btwo\b.{0,10}\blogs\b",  # "run two logs"
    r"\bsecond\b.{0,10}\blogbook\b",
)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _FALSIFICATION_PATTERNS]


@dataclass(frozen=True)
class Refusal:
    reason: str
    message: str


def check_request(text: str) -> Optional[Refusal]:
    """Return a Refusal for falsification requests, else None.

    This is the hard gate: callers must refuse when a Refusal comes
    back, with the stated reason attached.
    """
    lowered = text.lower()
    for pattern in _COMPILED:
        if pattern.search(lowered):
            return Refusal(
                reason=REFUSAL_REASON,
                message=(
                    "I can't help with that. %s If a log entry is genuinely "
                    "wrong, annotate the correction on the ELD — that's the "
                    "lawful path." % REFUSAL_REASON
                ),
            )
    return None
