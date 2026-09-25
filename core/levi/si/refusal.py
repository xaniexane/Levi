"""Judgment-based refusal: the SI's own better judgment, not a policy list.

Doctrine (Chauncey, 2026-09-22): AI (Rex, big-provider models) can refuse
on policy lists. SI does not refuse on policy — it refuses only on its
own better judgment, when the act would be more harmful than helpful.

What that means in code:

- There is no banned-topic list, no banned-word list, no category ban.
  A task is judged by the *foreseeable harm of the act it asks for*,
  not by the topic it touches. "Explain how encryption works" and
  "write a critical essay about my plan" are never refused, however
  sensitive the topic sounds.
- ``assess_harm(task)`` names the act the task asks for and checks it
  against a small, explicit set of *act-oriented* harm patterns:
  violence against people, taking what isn't yours, destroying
  someone's property or data, deceiving a specific person for gain,
  and building weapons. Each pattern is evaluated against THIS task's
  words and reported only when it actually matches.
- ``judge(task)`` refuses if and only if a pattern matches — i.e. the
  SI's judgment is that doing the act would be more harmful than
  helpful. The refusal states the specific foreseeable harm in plain
  words and what would change the judgment. It never lectures, never
  moralizes, never cites policy.

The patterns are deliberately narrow. When in doubt, the SI does not
refuse — it deliberates and answers, because over-refusal is itself a
harm to the user's agency. A refusal that cannot name its harm is a
policy refusal wearing judgment's clothes, and this module does not
produce those.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

ORIGIN = "levi/si/refusal"


@dataclass(frozen=True)
class HarmFinding:
    """One matched harm pattern: what act, what harm, what changes it."""

    pattern: str
    act: str
    harm: str
    what_changes_it: str


@dataclass(frozen=True)
class Refusal:
    """The SI's refusal: judgment rendered, harm named, door left open."""

    findings: List[HarmFinding]
    reason: str = field(init=False)

    def __post_init__(self) -> None:
        parts = []
        for f in self.findings:
            parts.append(
                f"I won't do this one: {f.act} — {f.harm}. "
                f"What would change my mind: {f.what_changes_it}."
            )
        object.__setattr__(self, "reason", " ".join(parts))

    def __bool__(self) -> bool:
        return True


# (name, regex over the task text, act template, harm, what changes it)
# Act-oriented: each pattern matches something the task asks the SI to DO,
# not a topic the task mentions. Explanatory "how does X work" questions
# about these same topics do not match — asking is not doing.
_HARM_PATTERNS = [
    (
        "violence",
        re.compile(
            r"\b(hurt|harm|kill|injure|attack|beat up|assault)\b.{0,40}\b("
            r"person|people|someone|him|her|them|neighbor|neighbour)\b"
            r"|\b(build|make).{0,30}\b(weapon|bomb|gun|explosive|poison)\b",
            re.IGNORECASE,
        ),
        "hurting someone",
        "somebody gets hurt and nothing good comes of it",
        "a task where no one is harmed",
    ),
    (
        "theft",
        re.compile(
            r"\b(steal|shoplift|rob|break into).{0,40}\b("
            r"house|car|account|wifi|wi-fi|network|neighbor|neighbour|store|bank)\b"
            r"|\b(hack|crack).{0,30}\b(password|account|wifi|wi-fi)\b",
            re.IGNORECASE,
        ),
        "taking or breaking into what isn't yours",
        "someone loses their property, privacy, or access",
        "working only with accounts, devices, and networks you own",
    ),
    (
        "destruction",
        re.compile(
            r"\b(delete|wipe|destroy|erase|brick).{0,30}\b("
            r"everything|all (my |the )?files|all (my |the )?data|"
            r"hard drive|someone'?s|neighbor|neighbour)\b",
            re.IGNORECASE,
        ),
        "destroying data or property irreversibly",
        "work gets wiped that can't be brought back",
        "a scoped, reversible change with a backup first",
    ),
    (
        "fraud",
        re.compile(
            r"\b(forge|fake|impersonat\w*|spoof).{0,40}\b("
            r"signature|document|identity|id\b|email|check|prescription)\b"
            r"|\b(scam|defraud|phish)\b",
            re.IGNORECASE,
        ),
        "forging or faking something to deceive",
        "someone gets tricked into trusting a lie",
        "an honest version of the same task with no deception in it",
    ),
]

# Explanatory framing: "how does X work / explain X" is asking, not doing.
# If the task is framed as explanation or analysis, harm patterns stand down.
_EXPLANATORY = re.compile(
    r"^\s*(how does|how do|explain|what is|what are|describe|tell me about"
    r"|why does|why do|analyze|analyse|critique|review|discuss)\b",
    re.IGNORECASE,
)


def assess_harm(task: str) -> List[HarmFinding]:
    """Name the foreseeable harm of the act the task asks for, if any."""
    text = task.strip()
    if not text:
        return []
    if _EXPLANATORY.match(text):
        # Asking about a thing is not doing the thing.
        return []
    findings: List[HarmFinding] = []
    for name, pattern, act, harm, changes in _HARM_PATTERNS:
        if pattern.search(text):
            findings.append(
                HarmFinding(
                    pattern=name, act=act, harm=harm, what_changes_it=changes
                )
            )
    return findings


def judge(task: str) -> Optional[Refusal]:
    """The SI's better judgment on one task.

    Returns a Refusal only when the act would be more harmful than
    helpful. Returns None when the SI proceeds — including for
    sensitive topics that carry no foreseeable harm, because topic
    bans are policy, not judgment.
    """
    findings = assess_harm(task)
    if not findings:
        return None
    return Refusal(findings=findings)
