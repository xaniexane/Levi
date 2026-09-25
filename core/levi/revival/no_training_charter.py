"""The no-training charter: a binding, versioned, plain-language guarantee.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 3]

The mechanism: the guarantee that *your code never trains anyone's model*
lives as a versioned ``Charter`` — numbered clauses in plain language,
append-only version history (a version is never edited in place; it is
superseded by a new one), a machine-readable consent record for the one
allowed exception (on-device-only assistance trained on your own corpus,
strictly opt-in), and a heuristic ``check`` that judges a proposed action
against the clauses and names the clauses it violates.

Design notes, kept honest:

- ``check`` is heuristic pattern matching over action descriptions, not
  legal reasoning. It catches the shapes it knows; silence is not
  permission. The docstring says so because the charter's whole point is
  that guarantees must be checkable, not merely asserted.
- A charter binds only the party that adopts it. ``adopted_by`` records
  who signed on; the module enforces nothing on anyone else — it is a
  promise with a checker, not a lock.
- Consent is per-user and revocable: ``revoke`` flips the record; actions
  after revocation check against the no-consent baseline.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/no-training-charter"

# Heuristic clause triggers: (clause id, regexes that suggest a violation).
_VIOLATION_PATTERNS: Dict[str, List[str]] = {
    "C1": [  # never train on user code
        r"train(ing|ed)?\s+(a|an|the|our|any)\s+model",
        r"model\s+training",
        r"fine[- ]?tune.*(on|with)\s+(user|your|customer)",
        r"(upload|send|ship|exfiltrate).*(code|repo|corpus).*train",
        r"telemetry.*code",
    ],
    "C2": [  # assistance stays on-device
        r"send\s+(code|repo|file|snippet|corpus)\s+to\s+(cloud|server|remote|api)",
        r"cloud\s+assist",
        r"remote\s+(inference|completion|analysis)\s+of\s+code",
    ],
    "C4": [  # consent required for on-device own-corpus training
        r"opt[- ]?in\s+training",
        r"train\s+on[- ]device.*without\s+consent",
    ],
}


@dataclass(frozen=True)
class Clause:
    """One numbered guarantee in plain language."""

    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Consent:
    """The one allowed exception, strictly opt-in and revocable."""

    user: str
    scope: str  # "on-device-own-corpus" or "none"
    granted_at: float
    charter_version: int
    revoked_at: float | None = None

    @property
    def active(self) -> bool:
        return self.scope != "none" and self.revoked_at is None


@dataclass
class CharterVersion:
    """One immutable version: clauses + plain-language rendering."""

    number: int
    clauses: List[Clause]
    adopted_by: str = ""
    adopted_at: float = field(default_factory=time.time)

    def render(self) -> str:
        lines = [
            f"# No-Training Charter — version {self.number}",
            "",
        ]
        if self.adopted_by:
            lines.append(f"Adopted by {self.adopted_by}.")
            lines.append("")
        for c in self.clauses:
            lines += [f"## {c.id} — {c.title}", "", c.text, ""]
        return "\n".join(lines).rstrip() + "\n"


class NoTrainingCharter:
    """The living charter: versioned guarantees, consent, and a checker."""

    def __init__(self, adopted_by: str = ""):
        self.adopted_by = adopted_by
        self._versions: List[CharterVersion] = [
            CharterVersion(1, self._base_clauses(), adopted_by)
        ]
        self._consents: Dict[str, Consent] = {}

    @staticmethod
    def _base_clauses() -> List[Clause]:
        return [
            Clause(
                "C1",
                "Your code never trains anyone's model",
                "Code, repositories, snippets, and commit history held in this "
                "code-home are never used to train, fine-tune, or evaluate any "
                "model — ours or anyone else's. No exceptions, no fine print.",
            ),
            Clause(
                "C2",
                "Assistance runs on your device",
                "Any AI assistance offered here runs on your own device, on "
                "your own machine. Your code is not sent to a cloud service "
                "for completion, analysis, or inference.",
            ),
            Clause(
                "C3",
                "Your corpus, your machine",
                "The only corpus any on-device assistant may learn from is "
                "your own — and only if you explicitly opt in. Other people's "
                "code is never mixed into your assistant's training.",
            ),
            Clause(
                "C4",
                "Opt-in is explicit and revocable",
                "On-device training on your own corpus requires your explicit "
                "opt-in, recorded with a timestamp and charter version. You "
                "may revoke it at any time; revocation takes effect "
                "immediately for all future training.",
            ),
            Clause(
                "C5",
                "Leave with everything",
                "You may export your entire code-home at any time (see the "
                "full-export bundle) and delete your data on request. The "
                "charter survives your departure: deletion means gone, not "
                "'retained for model improvement'.",
            ),
        ]

    # -- versions --------------------------------------------------------
    def current(self) -> CharterVersion:
        return self._versions[-1]

    def amend(self, new_clauses: List[Clause]) -> CharterVersion:
        """Supersede with a new version; history is append-only."""
        version = CharterVersion(
            number=self.current().number + 1,
            clauses=list(new_clauses),
            adopted_by=self.adopted_by,
        )
        self._versions.append(version)
        return version

    def history(self) -> List[CharterVersion]:
        return list(self._versions)

    # -- consent ----------------------------------------------------------
    def opt_in(self, user: str) -> Consent:
        consent = Consent(
            user=user,
            scope="on-device-own-corpus",
            granted_at=time.time(),
            charter_version=self.current().number,
        )
        self._consents[user] = consent
        return consent

    def revoke(self, user: str) -> Consent | None:
        existing = self._consents.get(user)
        if existing is None or not existing.active:
            return None
        revoked = Consent(
            user=existing.user,
            scope=existing.scope,
            granted_at=existing.granted_at,
            charter_version=existing.charter_version,
            revoked_at=time.time(),
        )
        self._consents[user] = revoked
        return revoked

    def consent_for(self, user: str) -> Consent | None:
        return self._consents.get(user)

    # -- the checker (heuristic, and it says so) --------------------------
    def check(self, action: Dict, user: str = "") -> Tuple[bool, List[str], List[str]]:
        """Judge a proposed action against the clauses.

        Returns (compliant, violated_clause_ids, notes). Heuristic: it
        matches action descriptions against known violation shapes.
        A clean result means "no known violation shape matched" — not
        a legal opinion.
        """
        description = " ".join(
            str(action.get(k, "")) for k in ("kind", "description", "destination")
        ).lower()
        violated: List[str] = []
        notes: List[str] = []
        for clause_id, patterns in _VIOLATION_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, description):
                    violated.append(clause_id)
                    notes.append(
                        f"action matches a known violation shape for {clause_id} "
                        f"(pattern: {pat!r})"
                    )
                    break

        # On-device own-corpus training is allowed only with active consent.
        if re.search(r"train", description) and re.search(r"on[- ]device", description):
            consent = self._consents.get(user)
            if consent is None or not consent.active:
                if "C4" not in violated:
                    violated.append("C4")
                    notes.append(
                        "on-device training needs an explicit opt-in; "
                        f"no active consent on record for {user or 'this user'}"
                    )

        compliant = not violated
        if compliant:
            notes.append(
                "no known violation shape matched (heuristic, not a legal opinion)"
            )
        return compliant, violated, notes
