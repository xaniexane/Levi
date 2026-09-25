"""SysOp culture as a method: ownership-as-stewardship.

Origin: the system operator, 1978-1996 — a person who kept a home PC and
phone line open to strangers, curated file libraries, ran door games,
moderated message areas, published ANSI art, and enforced local norms,
often spending hundreds of dollars a month on extra lines and hardware,
for status and love (documented across 200+ interviews in Jason Scott's
BBS: The Documentary, 2005). The mechanism: one human's taste, uptime
guarantee, and enforcement created a *place* rather than a *service*.
Rituals — new-user validation questionnaires, upload/download ratios,
published rules — manufactured belonging. The sysop was simultaneously
mayor, bouncer, librarian, and janitor, and the board's character was the
sysop's character.

What it is in LEVI: a Steward contract. The steward publishes a norms
document, sets an admission questionnaire with a passing rule, keeps an
upload/download ratio ledger that blocks downloads when the ratio
breaches, and applies sanctions on a strict escalation ladder
(warned -> suspended -> banned). Admission and ratio enforcement are the
load-bearing core: the questionnaire rites manufacture belonging, the
ratio ledger manufactures contribution.

Honesty label: LOAD-BEARING — admission questionnaire scoring and
ratio-ledger enforcement are concrete, transferable mechanisms.

Deny-closed inputs: empty board names, steward names, norms, user names
or answers; questionnaires with no questions or non-positive thresholds;
applications before a questionnaire exists, with wrong answer counts, or
from current/banned users; negative transfer sizes; downloads that breach
the ratio; and sanctions that skip ladder rungs all raise ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Board", "WARNED", "SUSPENDED", "BANNED"]

WARNED = "warned"
SUSPENDED = "suspended"
BANNED = "banned"
_SANCTIONS = (WARNED, SUSPENDED, BANNED)


@dataclass
class _Member:
    name: str
    uploaded_kb: float = 0.0
    downloaded_kb: float = 0.0
    sanction: str = ""  # "" | warned | suspended | banned


class Board:
    """One steward's place: norms, rites, ratios, sanctions."""

    def __init__(
        self,
        name: str,
        steward: str,
        norms: str,
        required_ratio: float = 0.5,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("board name must be a non-empty string")
        if not isinstance(steward, str) or not steward.strip():
            raise ValueError("steward name must be a non-empty string")
        if not isinstance(norms, str) or not norms.strip():
            raise ValueError("norms document must be non-empty")
        if required_ratio <= 0:
            raise ValueError("required_ratio must be positive")
        self.name = name.strip()
        self.steward = steward.strip()
        self.norms = norms.strip()
        self.required_ratio = required_ratio
        self._questions: list[str] = []
        self._min_answer_len = 0
        self._members: dict[str, _Member] = {}

    # -- admission rites ---------------------------------------------------
    def set_questionnaire(self, questions: list[str], min_answer_len: int = 10) -> None:
        """Publish the validation questionnaire: the admission rite."""
        if not questions:
            raise ValueError("questionnaire needs at least one question")
        cleaned: list[str] = []
        for q in questions:
            if not isinstance(q, str) or not q.strip():
                raise ValueError("questions must be non-empty strings")
            cleaned.append(q.strip())
        if min_answer_len < 1:
            raise ValueError("min_answer_len must be >= 1")
        self._questions = cleaned
        self._min_answer_len = min_answer_len

    def apply(self, user: str, answers: list[str]) -> tuple[bool, int]:
        """Answer the rite. Returns (admitted, score).

        Score = answers meeting the substance bar; admission needs all of
        them. The steward's taste is the passing rule.
        """
        user = self._require_user(user)
        if not self._questions:
            raise ValueError("no questionnaire published yet")
        if user in self._members:
            raise ValueError(f"{user!r} is already a member")
        if len(answers) != len(self._questions):
            raise ValueError(
                f"questionnaire has {len(self._questions)} questions, "
                f"got {len(answers)} answers"
            )
        for a in answers:
            if not isinstance(a, str) or not a.strip():
                raise ValueError("answers must be non-empty strings")
        score = sum(1 for a in answers if len(a.strip()) >= self._min_answer_len)
        admitted = score == len(self._questions)
        if admitted:
            self._members[user] = _Member(name=user)
        return admitted, score

    def members(self) -> list[str]:
        return sorted(self._members)

    # -- the ratio ledger ---------------------------------------------------
    def _get_member(self, user: str) -> _Member:
        user = self._require_user(user)
        member = self._members.get(user)
        if member is None:
            raise ValueError(f"{user!r} is not a member of {self.name!r}")
        return member

    def _require_member(self, user: str) -> _Member:
        member = self._get_member(user)
        if member.sanction == BANNED:
            raise ValueError(f"{user!r} is banned from {self.name!r}")
        return member

    @staticmethod
    def _require_user(user: str) -> str:
        if not isinstance(user, str) or not user.strip():
            raise ValueError("user name must be a non-empty string")
        return user.strip()

    def record_upload(self, user: str, kb: float) -> float:
        member = self._require_member(user)
        if kb <= 0:
            raise ValueError("upload size must be positive")
        member.uploaded_kb += kb
        return member.uploaded_kb

    def record_download(self, user: str, kb: float) -> float:
        """Download only if the ratio survives it — the ledger enforces."""
        member = self._require_member(user)
        if kb <= 0:
            raise ValueError("download size must be positive")
        if member.sanction == SUSPENDED:
            raise ValueError(f"{user!r} is suspended: no downloads")
        projected = member.uploaded_kb / (member.downloaded_kb + kb)
        if projected < self.required_ratio:
            raise ValueError(
                f"ratio violation: {user!r} has "
                f"{member.uploaded_kb:.1f} up / "
                f"{member.downloaded_kb:.1f} down; downloading {kb:.1f} KB "
                f"would drop the ratio to {projected:.2f} "
                f"(required {self.required_ratio}) — upload first"
            )
        member.downloaded_kb += kb
        return member.downloaded_kb

    def ratio(self, user: str) -> float:
        member = self._require_member(user)
        if member.downloaded_kb == 0:
            return float("inf") if member.uploaded_kb > 0 else 0.0
        return member.uploaded_kb / member.downloaded_kb

    # -- sanctions: the ladder ----------------------------------------------
    def sanction(self, user: str, level: str) -> str:
        """Escalate exactly one rung: warned -> suspended -> banned."""
        member = self._require_member(user)
        if level not in _SANCTIONS:
            raise ValueError(f"unknown sanction level: {level!r}")
        want = _SANCTIONS.index(level)
        have = _SANCTIONS.index(member.sanction) if member.sanction else -1
        if want == have:
            raise ValueError(f"{user!r} is already {level}")
        if want != have + 1:
            raise ValueError(
                f"sanctions escalate one rung at a time: {user!r} is "
                f"{member.sanction or 'in good standing'}, "
                f"cannot jump to {level}"
            )
        member.sanction = level
        return level

    def pardon(self, user: str) -> str:
        member = self._get_member(user)
        if not member.sanction:
            raise ValueError(f"{user!r} is in good standing: nothing to pardon")
        idx = _SANCTIONS.index(member.sanction)
        member.sanction = _SANCTIONS[idx - 1] if idx > 0 else ""
        return member.sanction or "member"
