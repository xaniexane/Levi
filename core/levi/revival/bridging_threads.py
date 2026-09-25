"""Discussion trees with bridging-aware ranking, plus portable identity.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 8]
(Reddit-density threading with bridging-aware ranking to counter the fluff
principle, plus portable identity).

This is an original, from-scratch implementation for LEVI. ``ThreadTree``
holds comments in a reply tree. Ranking deliberately fights two failure
modes of dense forums: (1) faction cheerleading — handled by the *bridging*
bonus, which rewards a comment when it earns endorsements from authors whose
declared stance *differs* from the comment's own; and (2) the fluff
principle (empty-but-loud content wins) — handled by a fluff penalty computed
from cheap, local heuristics (excessive caps, repeated tokens, pure
emoji/hype phrasing). The final order blends quality votes, the bridging
bonus, and the fluff penalty with visible weights, and ``explain()`` shows
the per-component breakdown for any comment.

Identity is portable: ``PortableIdentity`` derives a stable id from a key
hash (``key-id:<sha256>``) so the same author is recognizable across threads
and communities without a central registry. Endorsements are signed with
HMAC over the author's secret — any holder of the identity's verification
token can check them, nothing else is needed.

Honest limits: stance is *declared* by the author (self-reported, not
inferred — LEVI does not profile); the fluff penalty is heuristic and can
misjudge sincere enthusiasm; HMAC endorsement signing proves authorship to
verifiers who hold the secret, not public-key verifiability.

Public surface:
- ``ThreadTree``: ``post``, ``endorse``, ``rank``, ``explain``, ``thread``.
- ``PortableIdentity``: ``identity_id``, ``sign_endorsement``,
  ``verify_endorsement``.
- ``Comment``, ``RankWeights``, ``FluffError``/``ThreadError``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/bridging-threads"

_CAPS_RUN = re.compile(r"[A-Z]{5,}")
_REPEAT = re.compile(r"(\b\w+\b)(?:\s+\1){2,}", re.IGNORECASE)
_HYPE = re.compile(r"\b(lol|lmao|smh|wtf|omg|this|100%|!!!)\b", re.IGNORECASE)


class ThreadError(ValueError):
    """Raised for invalid thread operations."""


@dataclass
class PortableIdentity:
    """A portable author identity: stable id, HMAC-signed endorsements."""

    name: str
    secret: str = field(repr=False)
    stance: Optional[str] = None  # self-declared stance, e.g. "pro", "con", "neutral"

    @property
    def identity_id(self) -> str:
        return "key-id:" + hashlib.sha256(self.secret.encode()).hexdigest()[:16]

    def sign_endorsement(self, comment_id: int) -> str:
        return hmac.new(
            self.secret.encode(),
            f"endorse:{self.identity_id}:{comment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()[:32]

    def verify_endorsement(self, comment_id: int, signature: str) -> bool:
        return hmac.compare_digest(signature, self.sign_endorsement(comment_id))

    def card(self) -> Dict[str, str]:
        """The portable artifact: id + declared stance, safe to share."""
        return {
            "id": self.identity_id,
            "name": self.name,
            "stance": self.stance or "undeclared",
        }


@dataclass
class Comment:
    comment_id: int
    author: PortableIdentity
    text: str
    parent_id: Optional[int]
    children: List[int] = field(default_factory=list)
    votes: int = 0
    endorsements: List[Tuple[str, str, str]] = field(default_factory=list)
    # (endorser_id, endorser_stance, signature)


@dataclass(frozen=True)
class RankWeights:
    """Visible, tunable ranking weights. Nothing hidden."""

    quality: float = 1.0
    bridging: float = 1.5
    fluff_penalty: float = 1.0


class ThreadTree:
    """A reply tree ranked for bridging, penalized for fluff."""

    def __init__(self, weights: Optional[RankWeights] = None) -> None:
        self.weights = weights if weights is not None else RankWeights()
        self._comments: Dict[int, Comment] = {}
        self._roots: List[int] = []
        self._next_id = 1

    # -- posting ----------------------------------------------------------
    def post(
        self, author: PortableIdentity, text: str, parent_id: Optional[int] = None
    ) -> Comment:
        if not text.strip():
            raise ThreadError("comment text must be non-empty")
        if parent_id is not None and parent_id not in self._comments:
            raise ThreadError(f"no parent comment {parent_id}")
        comment = Comment(
            comment_id=self._next_id, author=author, text=text, parent_id=parent_id
        )
        self._next_id += 1
        self._comments[comment.comment_id] = comment
        if parent_id is None:
            self._roots.append(comment.comment_id)
        else:
            self._comments[parent_id].children.append(comment.comment_id)
        return comment

    def vote(self, comment_id: int, delta: int = 1) -> int:
        comment = self._get(comment_id)
        comment.votes += delta
        return comment.votes

    def endorse(self, endorser: PortableIdentity, comment_id: int) -> None:
        comment = self._get(comment_id)
        if endorser.identity_id == comment.author.identity_id:
            raise ThreadError("self-endorsement is not allowed")
        signature = endorser.sign_endorsement(comment_id)
        comment.endorsements.append(
            (endorser.identity_id, endorser.stance or "undeclared", signature)
        )

    # -- scoring ----------------------------------------------------------
    @staticmethod
    def fluff_score(text: str) -> float:
        """Heuristic 0..1 measure of fluffiness. Higher = fluffier."""
        if not text.strip():
            return 1.0
        words = text.split()
        if len(words) < 4:
            return 0.8  # drive-by one-liners are usually fluff
        caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / len(words)
        hype_hits = len(_HYPE.findall(text)) / len(words)
        repeat = 1.0 if _REPEAT.search(text) else 0.0
        bang = min(text.count("!") / 10.0, 1.0)
        score = 0.4 * min(caps_ratio * 5, 1.0) + 0.3 * min(hype_hits * 6, 1.0)
        score += 0.2 * repeat + 0.1 * bang
        return min(score, 1.0)

    def bridging_score(self, comment: Comment) -> float:
        """Fraction of verified endorsements crossing a stance boundary."""
        valid = 0
        cross = 0
        own_stance = comment.author.stance or "undeclared"
        for _endorser_id, stance, _signature in comment.endorsements:
            valid += 1
            if stance != own_stance and "undeclared" not in (stance, own_stance):
                cross += 1
        if valid == 0:
            return 0.0
        return cross / valid

    def quality_score(self, comment: Comment) -> float:
        return math.log1p(max(comment.votes, 0)) + 0.5 * len(comment.endorsements)

    def score(self, comment: Comment) -> float:
        w = self.weights
        return (
            w.quality * self.quality_score(comment)
            + w.bridging * self.bridging_score(comment) * 4.0
            - w.fluff_penalty * self.fluff_score(comment.text) * 3.0
        )

    def explain(self, comment_id: int) -> Dict[str, float]:
        """Visible per-component breakdown of a comment's score."""
        comment = self._get(comment_id)
        return {
            "quality": round(self.quality_score(comment), 3),
            "bridging": round(self.bridging_score(comment), 3),
            "fluff": round(self.fluff_score(comment.text), 3),
            "total": round(self.score(comment), 3),
        }

    def rank(self, limit: Optional[int] = None) -> List[int]:
        """All comment ids ordered best-first by bridging-aware score."""
        ordered = sorted(self._comments.values(), key=self.score, reverse=True)
        ids = [c.comment_id for c in ordered]
        return ids[:limit] if limit is not None else ids

    def thread(self, root_id: int) -> List[Tuple[int, int, str]]:
        """(comment_id, depth, text) depth-first walk of a reply tree."""
        root = self._get(root_id)
        out: List[Tuple[int, int, str]] = []

        def walk(comment: Comment, depth: int) -> None:
            out.append((comment.comment_id, depth, comment.text))
            for child_id in comment.children:
                walk(self._comments[child_id], depth + 1)

        walk(root, 0)
        return out

    # -- helpers ----------------------------------------------------------
    def _get(self, comment_id: int) -> Comment:
        try:
            return self._comments[comment_id]
        except KeyError as exc:
            raise ThreadError(f"no comment {comment_id}") from exc
