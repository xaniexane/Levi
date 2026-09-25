"""Core lint engine: regex rule matching with sentence-level excerpts."""

import re
from typing import Dict, List

from .rules import RULES

SEVERITIES = ("info", "caution", "hostile")

#: A finding about one hostile (or noteworthy) clause.
Finding = Dict[str, str]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def _sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    return parts


def _excerpt(text: str, pattern: str, window: int = 320) -> str:
    """Return the sentence(s) containing the first match, trimmed."""
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    for sentence in _sentences(text):
        if re.search(pattern, sentence, re.IGNORECASE):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if len(sentence) > window:
                # Keep the neighborhood around the actual match.
                local = re.search(pattern, sentence, re.IGNORECASE)
                start = max(0, local.start() - 120)
                end = min(len(sentence), local.end() + 120)
                prefix = "…" if start > 0 else ""
                suffix = "…" if end < len(sentence) else ""
                return prefix + sentence[start:end] + suffix
            return sentence
    # Fallback: raw window around the match in the full text.
    start = max(0, match.start() - 120)
    end = min(len(text), match.end() + 120)
    return "…" + re.sub(r"\s+", " ", text[start:end]).strip() + "…"


def lint(text: str) -> List[Finding]:
    """Scan terms text; return one finding per triggered rule (worst rule first)."""
    findings: List[Finding] = []
    seen_ids = set()
    for rule in RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                if rule["id"] in seen_ids:
                    break
                findings.append(
                    {
                        "rule_id": rule["id"],
                        "title": rule["title"],
                        "severity": rule["severity"],
                        "clause_excerpt": _excerpt(text, pattern),
                        "plain_language_flag": rule["plain_language_flag"],
                        "why_it_matters": rule.get("why_it_matters", ""),
                    }
                )
                seen_ids.add(rule["id"])
                break
    rank = {s: i for i, s in enumerate(reversed(SEVERITIES))}
    findings.sort(key=lambda f: rank[f["severity"]])
    return findings


def summarize(findings: List[Finding]) -> Dict[str, int]:
    """Count findings per severity band."""
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f["severity"]] += 1
    return counts


def lint_file(path: str) -> List[Finding]:
    """Lint a file on disk (utf-8, errors replaced)."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return lint(fh.read())
