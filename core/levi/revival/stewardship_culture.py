"""Ownership-as-stewardship: a place is its keeper's taste, uptime, and rules.

Studied from: dead-networks-20260916/report.md [SysOp culture as a method]
(ownership-as-stewardship: one human's taste, uptime, and enforcement make a
place; rituals — validation questionnaires, ratios, published rules —
manufacture belonging).

This is an original, from-scratch implementation for LEVI. A ``Stewardship``
models a single keeper running a place:

- *Taste*: a written charter plus *published rules* — the house rules are
  versioned and publicly listed, so enforcement is against a document, not a
  mood.
- *Uptime*: an uptime ledger. The steward logs availability windows; the
  module computes uptime ratio over a window. Reliability is the product.
- *Validation questionnaire*: newcomers answer a small ritual questionnaire
  (configured by the steward — questions, expected answers, pass threshold).
  Passing admits them; failing keeps them out until they retry. The ritual
  manufactures belonging: membership is earned, not granted.
- *Ratios*: members earn a contribution ratio (uploads/shared work versus
  downloads/taken). Falling below the steward's floor puts a member on
  probation; recovering restores good standing.
- *Enforcement*: the steward can warn, silence, or expel; every action is
  appended to a tamper-evident (hash-chained) enforcement log.

The mechanism is deliberately *personal*: there is one steward per
Stewardship. Accountability is the feature — a place with a named keeper.

Public surface:
- ``Stewardship``: ``publish_rules``, ``log_uptime``, ``uptime_ratio()``,
  ``set_questionnaire``, ``apply`` (take the questionnaire), ``record_share``
  / ``record_take``, ``ratio()``, ``warn`` / ``silence`` / ``expel``,
  ``enforcement_log()``, ``census()``.
- ``RuleSet``, ``StewardshipError`` for embedding.

stdlib-only. No network. Deterministic (clock-based uptime windows are
caller-supplied).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional, Tuple

ORIGIN = "levi-revival/stewardship-culture"


class StewardshipError(ValueError):
    """Raised when a stewardship operation cannot be honored."""


@dataclass(frozen=True)
class RuleSet:
    """Published house rules: versioned, listed, enforceable as written."""

    version: int
    rules: Tuple[str, ...]
    published_at: str = ""

    def __post_init__(self) -> None:
        if self.version < 1:
            raise StewardshipError("rule version must be >= 1")
        if not self.rules:
            raise StewardshipError("a rule set must contain at least one rule")
        if any(not r.strip() for r in self.rules):
            raise StewardshipError("rules must be non-empty strings")


@dataclass
class _Questionnaire:
    questions: List[Tuple[str, str]]  # (prompt, expected_answer)
    pass_threshold: float  # fraction of correct answers required


@dataclass
class _MemberRecord:
    handle: str
    admitted_at: str
    shares: int = 0
    takes: int = 0
    warnings: int = 0
    silenced: bool = False
    probation: bool = False


class Stewardship:
    """One keeper's place: taste (rules), uptime, rituals, ratios, enforcement."""

    def __init__(
        self,
        place_name: str,
        steward: str,
        ratio_floor: float = 0.5,
        charter: str = "",
    ) -> None:
        if not place_name or not steward:
            raise StewardshipError("place_name and steward must be non-empty")
        self.place_name = place_name
        self.steward = steward
        self.charter = charter
        self.ratio_floor = ratio_floor
        self._rules: List[RuleSet] = []
        self._uptime: List[Tuple[datetime, datetime]] = []  # (up, down) windows
        self._questionnaire: Optional[_Questionnaire] = None
        self._members: Dict[str, _MemberRecord] = {}
        self._ledger: List[str] = []

    # -- tamper-evident enforcement log -------------------------------------
    def _append_ledger(self, entry: str) -> None:
        prev = self._ledger[-1] if self._ledger else "GENESIS"
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        digest = hashlib.sha256(f"{prev}|{stamp}|{entry}".encode()).hexdigest()[:16]
        self._ledger.append(f"{stamp} {entry} [{digest}]")

    def enforcement_log(self) -> List[str]:
        return list(self._ledger)

    # -- taste: published rules ----------------------------------------------
    def publish_rules(self, rules: Tuple[str, ...]) -> RuleSet:
        version = len(self._rules) + 1
        ruleset = RuleSet(
            version=version,
            rules=rules,
            published_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._rules.append(ruleset)
        self._append_ledger(f"RULES v{version} count={len(rules)}")
        return ruleset

    def current_rules(self) -> Optional[RuleSet]:
        return self._rules[-1] if self._rules else None

    # -- uptime: the product is reliability ------------------------------------
    def log_uptime(self, up: datetime, down: datetime) -> None:
        """Log one availability window (up -> down, both timezone-aware)."""
        if down <= up:
            raise StewardshipError("down must be after up")
        self._uptime.append((up, down))

    def uptime_ratio(self, since: datetime, until: datetime) -> float:
        """Fraction of [since, until] the place was up."""
        if until <= since:
            raise StewardshipError("until must be after since")
        total = (until - since).total_seconds()
        up_secs = 0.0
        for up, down in self._uptime:
            start = max(up, since)
            end = min(down, until)
            if end > start:
                up_secs += (end - start).total_seconds()
        return round(min(up_secs / total, 1.0), 4)

    # -- ritual: the validation questionnaire -------------------------------------
    def set_questionnaire(
        self,
        questions: List[Tuple[str, str]],
        pass_threshold: float = 0.8,
    ) -> None:
        if not questions:
            raise StewardshipError("questionnaire needs at least one question")
        if not 0.0 < pass_threshold <= 1.0:
            raise StewardshipError("pass_threshold must be in (0, 1]")
        self._questionnaire = _Questionnaire(questions, pass_threshold)

    def apply(self, handle: str, answers: List[str]) -> Mapping[str, object]:
        """Take the validation ritual. Pass → membership; fail → retry later."""
        if self._questionnaire is None:
            raise StewardshipError("no questionnaire set")
        if not handle:
            raise StewardshipError("handle must be non-empty")
        if handle in self._members:
            raise StewardshipError(f"{handle!r} is already a member")
        q = self._questionnaire
        if len(answers) != len(q.questions):
            raise StewardshipError("answer count must match question count")
        correct = sum(
            1
            for ans, (_, expected) in zip(answers, q.questions, strict=True)
            if ans.strip().lower() == expected.strip().lower()
        )
        score = correct / len(q.questions)
        passed = score >= q.pass_threshold
        if passed:
            self._members[handle] = _MemberRecord(
                handle=handle,
                admitted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        self._append_ledger(
            f"RITUAL handle={handle} score={correct}/{len(q.questions)} "
            f"{'PASS' if passed else 'FAIL'}"
        )
        return {"passed": passed, "score": correct, "total": len(q.questions)}

    # -- ratios: contribution discipline -------------------------------------------
    def record_share(self, handle: str) -> None:
        self._require_member(handle).shares += 1
        self._check_ratio(handle)

    def record_take(self, handle: str) -> None:
        self._require_member(handle).takes += 1
        self._check_ratio(handle)

    def ratio(self, handle: str) -> float:
        """shares / max(takes, 1): a member must give as well as take."""
        rec = self._require_member(handle)
        return round(rec.shares / max(rec.takes, 1), 3)

    def _check_ratio(self, handle: str) -> None:
        rec = self._members[handle]
        if self.ratio(handle) < self.ratio_floor and not rec.probation:
            rec.probation = True
            self._append_ledger(f"PROBATION handle={handle} ratio={self.ratio(handle)}")
        elif self.ratio(handle) >= self.ratio_floor and rec.probation:
            rec.probation = False
            self._append_ledger(f"RESTORED handle={handle} ratio={self.ratio(handle)}")

    # -- enforcement: against the published rules -----------------------------------
    def _enforce(self, handle: str, action: str, rule: str) -> None:
        rec = self._require_member(handle)
        rules = self.current_rules()
        if rules is None:
            raise StewardshipError("no rules published; cannot enforce")
        if rule not in rules.rules:
            raise StewardshipError(f"{rule!r} is not a published rule")
        if action == "warn":
            rec.warnings += 1
        elif action == "silence":
            rec.silenced = True
        elif action == "expel":
            del self._members[handle]
        else:
            raise StewardshipError(f"unknown enforcement action {action!r}")
        self._append_ledger(f"ENFORCE {action.upper()} handle={handle} rule={rule!r}")

    def warn(self, handle: str, rule: str) -> None:
        self._enforce(handle, "warn", rule)

    def silence(self, handle: str, rule: str) -> None:
        self._enforce(handle, "silence", rule)

    def expel(self, handle: str, rule: str) -> None:
        self._enforce(handle, "expel", rule)

    def unsilence(self, handle: str) -> None:
        rec = self._require_member(handle)
        rec.silenced = False
        self._append_ledger(f"UNSILENCE handle={handle}")

    # -- queries ----------------------------------------------------------------------
    def is_member(self, handle: str) -> bool:
        return handle in self._members

    def is_silenced(self, handle: str) -> bool:
        return self._require_member(handle).silenced

    def census(self) -> Mapping[str, object]:
        return {
            "place": self.place_name,
            "steward": self.steward,
            "members": len(self._members),
            "on_probation": sum(1 for r in self._members.values() if r.probation),
            "silenced": sum(1 for r in self._members.values() if r.silenced),
            "rule_versions": len(self._rules),
            "enforcement_actions": len(self._ledger),
        }

    def _require_member(self, handle: str) -> _MemberRecord:
        try:
            return self._members[handle]
        except KeyError:
            raise StewardshipError(f"unknown member {handle!r}") from None
