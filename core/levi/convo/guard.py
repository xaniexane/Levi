"""The immune sense: contradiction detection for conversation.

Nothing here censors or blocks. :func:`check_contradictions` compares a new
reply's claims against established session facts and returns structured
*findings*; the caller decides what to do with them (surface a gentle
"earlier you said…", log, ignore).

Heuristics, precision over recall: direct negations ("X is Y" vs "X is not
Y") and entity-attribute conflicts ("nginx runs on 8080" vs "nginx runs on
9090"). It would rather miss a subtle contradiction than hallucinate one.
Deterministic.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from levi.convo.state import _sentences, _CLAIM_HINT_RE, _content_words


def _subjects_match(a: str, b: str) -> bool:
    """Do two attribute-subjects refer to the same thing? Content-word
    Jaccard >= 0.5. Substring matching was too loose ("nginx" matched
    "got it the nginx migration"); this keeps the precision-over-recall
    contract."""
    sa, sb = set(_content_words(a)), set(_content_words(b))
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= 0.5


_NEG_WORDS = {"not", "never", "no", "cannot", "cant"}
_AUX = {
    "do",
    "does",
    "did",
    "be",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "will",
    "would",
    "can",
    "could",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "ought",
}
_INFLECT = {
    "runs": "run",
    "uses": "use",
    "goes": "go",
    "says": "say",
    "has": "have",
    "does": "do",
}
_CONTRACT = {
    "can't": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "couldn't": "could not",
    "wouldn't": "would not",
    "shouldn't": "should not",
}
_ATTR_RE = re.compile(
    r"^(.+?)\s+(is|are|was|were|runs|run|uses|use|has|have)\s+(.+)$",
    re.IGNORECASE,
)
_DISCOURSE_RE = re.compile(
    r"^(?:yes|yeah|yep|no|nope|right|sure|okay|ok)\b[\s\u2014\u2013\-:]*",
)


def _strip_discourse(text: str) -> str:
    """Drop leading discourse markers ("Yes —", "No -") that would otherwise
    poison subject matching in the attribute-conflict check."""
    return _DISCOURSE_RE.sub("", text).strip()


_PUNCT_RE = re.compile(r"[^\w\s]")


def _g_tokens(text: str) -> List[str]:
    """Negation-aware tokens: lowercase, contractions expanded, light
    inflection fold. Unlike the retrieval tokenizer, negation words and
    auxiliaries are KEPT here — they are the signal."""
    text = text.lower()
    for k, v in _CONTRACT.items():
        text = re.sub(r"\b%s\b" % re.escape(k), v, text)
    text = re.sub(r"n't\b", " not", text)
    text = _PUNCT_RE.sub(" ", text)
    return [_INFLECT.get(t, t) for t in text.split() if len(t) >= 2]


def _claim_sig(text: str) -> Tuple[bool, List[str]]:
    """(has_negation, sorted content tokens) for a claim."""
    toks = _g_tokens(text)
    neg = any(t in _NEG_WORDS for t in toks)
    rest = sorted(t for t in toks if t not in _NEG_WORDS and t not in _AUX)
    return neg, rest


def _clean(text: str) -> str:
    return " ".join(_g_tokens(text))


def _is_direct_negation(claim: str, fact: str) -> bool:
    """Same claim, different negation signal ("X is Y" vs "X is not Y").

    Negation is presence-based, not parity-based: a leading discourse "No —"
    plus "does not" is one denial, not a double negative.
    """
    neg_c, rest_c = _claim_sig(claim)
    neg_f, rest_f = _claim_sig(fact)
    return rest_c == rest_f and len(rest_c) >= 3 and neg_c != neg_f


def _is_attribute_conflict(claim: str, fact: str) -> bool:
    """Same subject, different attribute ("runs on 8080" vs "runs on 9090")."""
    mc = _ATTR_RE.match(_strip_discourse(_clean(claim)))
    mf = _ATTR_RE.match(_strip_discourse(_clean(fact)))
    if not (mc and mf):
        return False
    subj_c, attr_c = mc.group(1).strip(), mc.group(3).strip()
    subj_f, attr_f = mf.group(1).strip(), mf.group(3).strip()
    if not subj_c or not subj_f or not attr_c or not attr_f:
        return False
    # same predicate verb required: "runs on 9090" vs "is on my radar" are
    # different predicates about the same subject, not a conflict.
    if mc.group(2).lower() != mf.group(2).lower():
        return False
    # attributes differ and neither merely extends the other
    diff_attr = attr_c != attr_f and attr_c not in attr_f and attr_f not in attr_c
    return bool(_subjects_match(subj_c, subj_f) and diff_attr)


def extract_claims(text: str) -> List[str]:
    """Pull claim-shaped sentences out of a reply."""
    return [s for s in _sentences(text or "") if _CLAIM_HINT_RE.search(s)]


def check_contradictions(reply_text: str, facts: List[Dict]) -> List[Dict]:
    """Flag contradictions between *reply_text* and established *facts*.

    *facts* is a list of ``{"text": str, "turn": int}``. Returns findings:
    ``{"type": "direct_negation"|"attribute_conflict", "reply": str,
    "fact": str, "fact_turn": int}``. Empty list means clean.
    """
    findings: List[Dict] = []
    if not reply_text or not facts:
        return findings
    seen = set()
    for claim in extract_claims(reply_text):
        for fact in facts:
            ftext = fact.get("text", "")
            if not ftext:
                continue
            kind = None
            if _is_direct_negation(claim, ftext):
                kind = "direct_negation"
            elif _is_attribute_conflict(claim, ftext):
                kind = "attribute_conflict"
            if kind:
                key = (kind, claim, ftext)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "type": kind,
                        "reply": claim,
                        "fact": ftext,
                        "fact_turn": fact.get("turn"),
                    }
                )
    return findings
