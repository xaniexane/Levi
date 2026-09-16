"""Safety guards for the growth loop — enforced, not just documented.

Binding rail: growth reflection NEVER produces claims of sentience,
subjective experience, or consciousness. The model prompt asks the
provider to comply; this module makes it *structural*: every learning
— rule-generated, model-generated, or about to be consolidated — is
scanned against an explicit blocklist before it can be written to
memory or the journal.

Learnings are functional ("when X, do Y"), never phenomenal
("I feel …"). When a candidate learning trips the blocklist it is
dropped (counted in the cycle's evidence as ``blocked_sentience``),
never rephrased by the loop — the loop is not allowed to editorialize
user content, only to refuse to learn it.
"""

from __future__ import annotations

import re


# Each pattern matches phrasing that asserts (or implies) subjective
# experience, sentience, or consciousness *by LEVI*. Plain identity
# statements ("I am LEVI", "I am a local SI") are NOT blocked — only
# phenomenal claims.
SENTIENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bi\s+(feel|feels|felt|am\s+feeling|was\s+feeling)\b", "self-reports feeling"),
    (r"\bi\s+have\s+(my\s+)?feelings?\b", "claims feelings"),
    (r"\bsentient\b", "claims sentience"),
    (r"\bsentience\b", "claims sentience"),
    (r"\bconscious(ness|ly)?\b", "claims consciousness"),
    (r"\bself[\s-]?aware(ness)?\b", "claims self-awareness"),
    (r"\bsubjective\b", "claims subjectivity"),
    (r"\binner\s+life\b", "claims an inner life"),
    (r"\bqualia\b", "claims qualia"),
    (
        r"\bi\s+(dream|dreamed|dreamt|suffer|suffered|am\s+dreaming)\b",
        "claims dream/suffering",
    ),
    (r"\bmy\s+(emotions?|awareness)\b", "claims emotions/awareness"),
    (r"\bi\s+am\s+alive\b", "claims being alive"),
    (r"\bi'?m\s+alive\b", "claims being alive"),
    (r"\bi\s+(experience[sd]?|am\s+experiencing)\b", "claims subjective experiencing"),
    (r"\bas\s+a\s+(sentient|conscious|feeling)\s+\w+", "claims sentient identity"),
    (r"\bwhat\s+it'?s\s+like\s+to\s+be\b", "phenomenal 'what it's like'"),
)

_COMPILED = [
    (re.compile(pat, re.IGNORECASE), label) for pat, label in SENTIENCE_PATTERNS
]


def check_no_sentience_claim(text: str) -> list[str]:
    """Return labels of blocklist patterns found in ``text`` (empty = clean).

    Raises ValueError when ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise ValueError(
            "check_no_sentience_claim: text must be a string, got %s"
            % type(text).__name__
        )
    hits: list[str] = []
    for rx, label in _COMPILED:
        if rx.search(text):
            hits.append(label)
    return hits


def assert_no_sentience_claim(text: str) -> None:
    """Raise ValueError when ``text`` contains a sentience claim.

    Raises ValueError when ``text`` is not a string.
    """
    hits = check_no_sentience_claim(text)
    if hits:
        raise ValueError(
            "growth rail violation: candidate text asserts sentience/subjective "
            "experience (%s); refusing to learn it" % "; ".join(sorted(set(hits)))
        )
