"""Memory write path: extract → resolve → scope → retrieve.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.7)

Functional description: the universal loop every memory write passes
through —

1. extract: pull candidate facts out of a turn (here: a simple
   subject-verb-object style pattern extractor, honestly rule-based);
2. resolve: each candidate is classified ADD / UPDATE / DELETE / NOOP
   against what is already stored, keyed by subject;
3. scope: each write is tagged with its scope (session / user / global)
   so a session-local preference never overwrites a global fact;
4. retrieve: after writing, return the affected records as confirmation.

Reconciliation OVERWRITES contradictions rather than hoarding both
versions: an UPDATE replaces the old text, a DELETE removes it, and every
resolution decision is appended to a log with its reason — the log is the
audit trail, not a second copy of the facts.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/memwrite"

# resolution decisions
ADD = "ADD"
UPDATE = "UPDATE"
DELETE = "DELETE"
NOOP = "NOOP"

# scopes
SESSION = "session"
USER = "user"
GLOBAL = "global"

# crude fact patterns: "X is Y", "X likes Y", "X has Y", "my X is Y"
_FACT = re.compile(
    r"(?i)\b(my\s+)?([a-z][a-z0-9 _-]{1,40}?)\s+"
    r"(is|are|was|were|likes?|loves?|hates?|prefers?|has|have|owns?)\s+"
    r"([a-z0-9][^.!?;]{1,120})"
)
_NEG = re.compile(r"(?i)\b(no longer|not|n't|never|don't|doesn't|isn't)\b")


@dataclass
class Candidate:
    subject: str
    text: str
    negated: bool = False


@dataclass
class Record:
    subject: str
    text: str
    scope: str
    version: int = 1


@dataclass
class Resolution:
    decision: str
    subject: str
    reason: str
    old_text: Optional[str] = None
    new_text: Optional[str] = None


def extract_candidates(turn: str) -> List[Candidate]:
    """Rule-based extraction. Honest about its limits: it catches simple
    declarative facts and misses everything subtle."""
    out: List[Candidate] = []
    for m in _FACT.finditer(turn):
        mine, subject, verb, obj = m.groups()
        subject = subject.strip().lower()
        text = f"{subject} {verb.lower()} {obj.strip()}"
        if mine:
            text = "my " + text
        out.append(
            Candidate(subject=subject, text=text, negated=bool(_NEG.search(m.group(0))))
        )
    return out


class MemoryWriter:
    """The universal write loop with an audited resolution log."""

    def __init__(self) -> None:
        # (scope, subject) -> Record
        self.store: Dict[Tuple[str, str], Record] = {}
        self.log: List[Resolution] = []

    def _resolve(self, cand: Candidate, scope: str) -> Resolution:
        key = (scope, cand.subject)
        existing = self.store.get(key)
        if existing is None:
            if cand.negated:
                return Resolution(
                    NOOP,
                    cand.subject,
                    "negated claim about unknown subject; nothing to delete",
                )
            return Resolution(
                ADD, cand.subject, "new subject in this scope", new_text=cand.text
            )
        if cand.negated:
            return Resolution(
                DELETE,
                cand.subject,
                "explicit negation of stored fact; removing "
                "rather than hoarding the contradiction",
                old_text=existing.text,
            )
        if cand.text.strip().lower() == existing.text.strip().lower():
            return Resolution(NOOP, cand.subject, "identical to stored fact; no change")
        return Resolution(
            UPDATE,
            cand.subject,
            "contradicts stored fact; overwriting with the newer claim",
            old_text=existing.text,
            new_text=cand.text,
        )

    def _apply(self, res: Resolution, scope: str) -> None:
        key = (scope, res.subject)
        if res.decision == ADD:
            self.store[key] = Record(
                subject=res.subject, text=res.new_text or "", scope=scope, version=1
            )
        elif res.decision == UPDATE and res.new_text is not None:
            old = self.store[key]
            self.store[key] = Record(
                subject=res.subject,
                text=res.new_text,
                scope=scope,
                version=old.version + 1,
            )
        elif res.decision == DELETE:
            self.store.pop(key, None)
        # NOOP: touch nothing

    def write(self, turn: str, scope: str = SESSION) -> List[Resolution]:
        """extract → resolve → scope → retrieve. Returns the resolutions."""
        resolutions: List[Resolution] = []
        for cand in extract_candidates(turn):
            res = self._resolve(cand, scope)
            self._apply(res, scope)
            self.log.append(res)
            resolutions.append(res)
        return resolutions

    def retrieve(self, subject: str, scope: Optional[str] = None) -> List[Record]:
        """Read back what a write affected. Scope narrows; None = all."""
        out = []
        for (sc, _subj), rec in self.store.items():
            if rec.subject == subject.lower() and (scope is None or sc == scope):
                out.append(rec)
        return out

    def decisions_for(self, subject: str) -> List[Resolution]:
        return [r for r in self.log if r.subject == subject.lower()]
