"""Multi-lock quorum custody as tamper resistance + auditable skill lineage.

Studied from: lost-crafts-20260916/report.md [Batch 1] (the Zunftlade, the
guild chest: opened only when several key-holders turn their locks together —
quorum custody — and the apprenticeship registers kept inside as an auditable
skill lineage).

This is an original, from-scratch implementation for LEVI. A ``QuorumChest``
has N key-holders and opens only when at least K distinct holders present
their keys within one session (K-of-N quorum, Shamir-style logic but pure
bookkeeping — no crypto claims beyond a tamper-evident hash chain). Contents
are sealed envelopes; opening requires quorum and every opening, deposit, and
withdrawal is appended to an append-only, hash-chained audit log. The chest
also keeps the *apprenticeship register*: learner entries linked to
sponsor -> master chains, so skill lineage is auditable — who taught whom,
when, and what rank was granted.

Tamper resistance is honest and bounded: the hash chain detects log edits
after the fact (``audit()`` re-verifies the chain); it does not prevent a
sufficiently motivated attacker — the docstring says so.

Public surface:
- ``QuorumChest``: ``deposit(env, contents, sealer)``, ``open_session(keys)``,
  ``withdraw(env, session)``, ``register_learner(...)``, ``lineage(learner)``,
  ``audit()``.
- ``Session`` (a quorum opening), ``QuorumError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

ORIGIN = "levi-revival/quorum-chest"


class QuorumError(ValueError):
    """Raised when a quorum or custody rule cannot be honored."""


@dataclass(frozen=True)
class Session:
    """One quorum opening: the distinct key-holders who turned their keys."""

    holders: frozenset
    stamp: str


@dataclass
class LineageEntry:
    learner: str
    rank: str
    sponsor: str
    stamp: str


class QuorumChest:
    """K-of-N quorum custody with a hash-chained audit log and registers."""

    def __init__(self, holders: Set[str], quorum: int) -> None:
        holders = set(holders)
        if len(holders) < 2:
            raise QuorumError("a chest needs at least 2 key-holders")
        if not 1 <= quorum <= len(holders):
            raise QuorumError("quorum must be between 1 and the number of holders")
        self._holders = holders
        self._quorum = quorum
        self._contents: Dict[str, str] = {}
        self._sealers: Dict[str, str] = {}
        self._log: List[str] = []
        self._register: List[LineageEntry] = []
        self._append("CHEST-FOUNDED", f"holders={sorted(holders)} quorum={quorum}")

    # -- audit log ---------------------------------------------------------
    def _append(self, action: str, detail: str) -> None:
        prev = self._log[-1] if self._log else "GENESIS"
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        digest = hashlib.sha256(
            f"{prev}|{stamp}|{action}|{detail}".encode()
        ).hexdigest()
        self._log.append(f"{stamp} {action} {detail} [{digest[:16]}]")

    def audit(self) -> bool:
        """Re-verify the hash chain. True iff no log entry was altered."""
        prev = "GENESIS"
        for entry in self._log:
            # entry format: "<stamp> <action> <detail> [<digest>]"
            digest = entry.rsplit("[", 1)[1].rstrip("]")
            body = entry.rsplit(" [", 1)[0]
            stamp, action, detail = body.split(" ", 2)
            expect = hashlib.sha256(
                f"{prev}|{stamp}|{action}|{detail}".encode()
            ).hexdigest()[:16]
            if expect != digest:
                return False
            prev = entry
        return True

    def log(self) -> List[str]:
        return list(self._log)

    # -- quorum -------------------------------------------------------------
    @property
    def quorum(self) -> int:
        return self._quorum

    def open_session(self, keys: Set[str]) -> Session:
        """Present key-holders' keys; returns a session iff quorum is met."""
        keys = set(keys)
        unknown = keys - self._holders
        if unknown:
            raise QuorumError(f"unknown key-holders: {sorted(unknown)}")
        if len(keys) < self._quorum:
            raise QuorumError(
                f"quorum not met: {len(keys)} keys presented, need {self._quorum}"
            )
        session = Session(
            holders=frozenset(keys),
            stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._append("OPENED", f"by={sorted(keys)}")
        return session

    def _require_open(self, session: Optional[Session]) -> None:
        if session is None or not (session.holders <= self._holders):
            raise QuorumError("a valid quorum session is required")
        if len(session.holders) < self._quorum:
            raise QuorumError("session does not meet quorum")

    # -- custody ------------------------------------------------------------
    def deposit(self, envelope: str, contents: str, sealer: str) -> None:
        if envelope in self._contents:
            raise QuorumError(f"envelope {envelope!r} already sealed")
        self._contents[envelope] = contents
        self._sealers[envelope] = sealer
        self._append("DEPOSIT", f"envelope={envelope} sealer={sealer}")

    def withdraw(self, envelope: str, session: Session) -> str:
        self._require_open(session)
        if envelope not in self._contents:
            raise QuorumError(f"no envelope {envelope!r}")
        contents = self._contents.pop(envelope)
        sealer = self._sealers.pop(envelope)
        self._append(
            "WITHDRAW",
            f"envelope={envelope} sealer={sealer} by={sorted(session.holders)}",
        )
        return contents

    def inventory(self, session: Session) -> List[str]:
        self._require_open(session)
        self._append("INVENTORY", f"by={sorted(session.holders)}")
        return sorted(self._contents)

    # -- apprenticeship register: auditable skill lineage -------------------
    def register_learner(
        self, learner: str, rank: str, sponsor: str, session: Session
    ) -> LineageEntry:
        """Record rank granted to a learner under quorum witness. The sponsor
        chain is the auditable skill lineage."""
        self._require_open(session)
        if sponsor not in self._holders:
            raise QuorumError(f"sponsor {sponsor!r} is not a key-holder of this chest")
        entry = LineageEntry(
            learner=learner,
            rank=rank,
            sponsor=sponsor,
            stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._register.append(entry)
        self._append("REGISTER", f"learner={learner} rank={rank} sponsor={sponsor}")
        return entry

    def lineage(self, learner: str) -> List[LineageEntry]:
        """All register entries for a learner: who granted what, when."""
        return [e for e in self._register if e.learner == learner]

    def register_all(self) -> List[LineageEntry]:
        return list(self._register)
