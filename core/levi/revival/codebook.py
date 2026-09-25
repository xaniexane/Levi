"""LEVI's synchronized codebook channel: lossy compression by shared dictionary.

Studied from: forgotten-methods-wave3-20260916-0015/report.md
(method #34 Commercial Telegraph Codebooks + method #37 Chappe Semaphore
Codebook, MERGED)

Two old mechanisms, one shared trick:

* A commercial telegraph codebook replaces whole phrases with short tokens.
  Both sender and receiver hold the same book; the wire carries tokens, the
  book carries the meaning. The failure mode is never in the tokens — it is
  in the *books diverging*. A sender on edition 7 and a receiver on edition
  6 do not disagree about tokens; they disagree silently, which is worse.

* The Chappe semaphore codebook addressed meaning in two dimensions: a page
  signal, then an entry signal inside that page — a pair of hops into a
  shared phrase-space, with each symbol acknowledged before the next one
  moved. Slow, visible, and strictly gated by confirmation.

This module merges them into one mechanism: a shared token↔phrase dictionary
with mandatory version/hash synchronization *before* any encode/decode is
allowed, plus a two-dimensional addressing mode (page + entry signals) with
per-symbol acknowledgment and flow control. Compression is lossy by design —
the book holds one canonical phrasing per meaning — and the sync check is
the load-bearing wall.

Usage pattern::

    alice = CodebookParty("alice", DEFAULT_CODEBOOK)
    bob   = CodebookParty("bob",   DEFAULT_CODEBOOK)
    assert alice.sync_with(bob)          # hash handshake first
    wire  = alice.encode("delayed: supply ship arrival")
    bob.decode(wire)                    # -> the canonical phrase

Unsynced parties raise :class:`UnsyncedCodebookError` on encode *and*
decode. That refusal is the feature.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

ORIGIN = "levi-revival/codebook"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnsyncedCodebookError(Exception):
    """Raised when a party tries to use a codebook that is not synchronized."""


class UnknownTokenError(Exception):
    """Raised on decode when a token is absent from the book."""


class UncodedPhraseError(Exception):
    """Raised on encode when no token covers the phrase and none is allowed."""


# ---------------------------------------------------------------------------
# The shared dictionary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Codebook:
    """An immutable edition of the shared token↔phrase dictionary."""

    version: str
    entries: Tuple[Tuple[str, str], ...]  # (token, phrase) pairs

    @property
    def token_to_phrase(self) -> Dict[str, str]:
        return {t: p for t, p in self.entries}

    @property
    def phrase_to_token(self) -> Dict[str, str]:
        return {p: t for t, p in self.entries}

    @property
    def fingerprint(self) -> str:
        """Content hash of this edition. Sync is verified by comparing these."""
        canonical = json.dumps(
            {"version": self.version, "entries": list(self.entries)},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def derived(self, version: str, extra: Iterable[Tuple[str, str]]) -> "Codebook":
        """Return a new edition with extra entries (simulates book drift)."""
        return Codebook(version=version, entries=self.entries + tuple(extra))


# A small original book: fifteen phrases, short tokens. Any book works;
# this one ships as the demo default.
DEFAULT_CODEBOOK = Codebook(
    version="7",
    entries=tuple(
        [
            ("A1", "arrival delayed"),
            ("A2", "departure confirmed"),
            ("B1", "request supplies"),
            ("B2", "supplies dispatched"),
            ("C1", "position unchanged"),
            ("C2", "position changed"),
            ("D1", "weather adverse"),
            ("D2", "weather favorable"),
            ("E1", "awaiting orders"),
            ("E2", "orders received"),
            ("F1", "request reinforcement"),
            ("F2", "reinforcement dispatched"),
            ("G1", "all clear"),
            ("G2", "urgent: respond immediately"),
            ("H1", "cease operations"),
        ]
    ),
)


# ---------------------------------------------------------------------------
# Parties and the sync handshake
# ---------------------------------------------------------------------------


class CodebookParty:
    """One endpoint of the channel. Holds a book and sync state."""

    def __init__(self, name: str, codebook: Codebook) -> None:
        self.name = name
        self.codebook = codebook
        self._synced_parties: Dict[str, str] = {}  # name -> confirmed fingerprint

    # -- sync -------------------------------------------------------------

    def sync_with(self, other: "CodebookParty") -> bool:
        """Version/hash handshake. True iff both books are identical.

        Records the sync on both sides only on success.
        """
        mine, theirs = self.codebook.fingerprint, other.codebook.fingerprint
        if mine != theirs:
            return False
        self._synced_parties[other.name] = mine
        other._synced_parties[self.name] = theirs
        return True

    def synced_with(self, other: "CodebookParty") -> bool:
        return self._synced_parties.get(other.name) == self.codebook.fingerprint

    def _require_sync(self, other: "CodebookParty") -> None:
        if not self.synced_with(other):
            raise UnsyncedCodebookError(
                f"{self.name} cannot exchange with {other.name}: "
                "codebook not synchronized (run sync_with first)"
            )

    # -- encode / decode --------------------------------------------------

    def encode(self, phrase: str, other: "CodebookParty") -> str:
        """Compress a phrase to its token. Requires sync with the receiver."""
        self._require_sync(other)
        table = self.codebook.phrase_to_token
        if phrase not in table:
            raise UncodedPhraseError(f"no token for phrase: {phrase!r}")
        return table[phrase]

    def decode(self, token: str, other: "CodebookParty") -> str:
        """Expand a token to its phrase. Requires sync with the sender."""
        self._require_sync(other)
        table = self.codebook.token_to_phrase
        if token not in table:
            raise UnknownTokenError(f"unknown token: {token!r}")
        return table[token]

    def encode_all(self, phrases: List[str], other: "CodebookParty") -> List[str]:
        return [self.encode(p, other) for p in phrases]

    def decode_all(self, tokens: List[str], other: "CodebookParty") -> List[str]:
        return [self.decode(t, other) for t in tokens]


# ---------------------------------------------------------------------------
# Chappe half: two-dimensional addressing with per-symbol ack + flow control
# ---------------------------------------------------------------------------


@dataclass
class SymbolLedger:
    """Per-symbol acknowledgment log for a two-hop transmission."""

    entries: List[Dict[str, str]] = field(default_factory=list)

    def record(self, hop: str, signal: str, ack: str) -> None:
        self.entries.append({"hop": hop, "signal": signal, "ack": ack})

    @property
    def acknowledged(self) -> bool:
        return all(e["ack"] == "ACK" for e in self.entries) and bool(self.entries)


class SemaphoreSession:
    """Two-dimensional addressing into a shared phrase-space.

    A phrase is addressed as (page, entry): the sender raises a *page
    signal*, waits for an ACK, then raises the *entry signal* and waits for
    a second ACK. Flow control: the sender may not emit the entry signal
    until the page signal is acknowledged, and may not emit the next page
    until the entry is acknowledged. ``page_size`` phrases share a page.
    """

    PAGE_ACK = "ACK"
    PAGE_NAK = "NAK"

    def __init__(self, party: CodebookParty, page_size: int = 4) -> None:
        self.party = party
        self.page_size = page_size
        self.phrases: List[str] = [p for _, p in party.codebook.entries]
        self.ledger = SymbolLedger()
        self._pending_page: Optional[int] = None

    # -- receiver side: acknowledging signals ------------------------------

    def ack_page_signal(self, page: int) -> str:
        """Receiver acknowledges a page signal; NAK if the page is out of range."""
        pages = self.page_count
        ack = self.PAGE_ACK if 0 <= page < pages else self.PAGE_NAK
        self.ledger.record("page", str(page), ack)
        if ack == self.PAGE_ACK:
            self._pending_page = page
        return ack

    def ack_entry_signal(self, entry: int) -> Tuple[str, Optional[str]]:
        """Receiver acknowledges an entry signal; resolves the phrase on ACK."""
        if self._pending_page is None:
            self.ledger.record("entry", str(entry), self.PAGE_NAK)
            return self.PAGE_NAK, None
        page_start = self._pending_page * self.page_size
        index = page_start + entry
        if not (page_start <= index < page_start + self.page_size) or index >= len(
            self.phrases
        ):
            self.ledger.record("entry", str(entry), self.PAGE_NAK)
            return self.PAGE_NAK, None
        self.ledger.record("entry", str(entry), self.PAGE_ACK)
        phrase = self.phrases[index]
        self._pending_page = None  # flow control: page consumed
        return self.PAGE_ACK, phrase

    # -- sender side: driving a transmission --------------------------------

    @property
    def page_count(self) -> int:
        return (len(self.phrases) + self.page_size - 1) // self.page_size

    def address_of(self, phrase: str) -> Tuple[int, int]:
        """(page, entry) address of a phrase in the shared phrase-space."""
        index = self.phrases.index(phrase)
        return index // self.page_size, index % self.page_size

    def transmit(self, phrase: str, receiver: "SemaphoreSession") -> Optional[str]:
        """Send one phrase: page signal → ACK → entry signal → ACK.

        Flow control is enforced by the receiver's acks; a NAK at any hop
        aborts and returns None.
        """
        if self.party.codebook.fingerprint != receiver.party.codebook.fingerprint:
            raise UnsyncedCodebookError(
                "semaphore session requires synchronized codebooks"
            )
        page, entry = self.address_of(phrase)
        if receiver.ack_page_signal(page) != self.PAGE_ACK:
            return None
        ack, resolved = receiver.ack_entry_signal(entry)
        if ack != self.PAGE_ACK:
            return None
        return resolved


def demo() -> Dict[str, object]:
    """End-to-end: sync, token exchange, then a semaphore transmission."""
    alice = CodebookParty("alice", DEFAULT_CODEBOOK)
    bob = CodebookParty("bob", DEFAULT_CODEBOOK)
    synced = alice.sync_with(bob)
    token = alice.encode("arrival delayed", bob)
    phrase = bob.decode(token, alice)
    session_a = SemaphoreSession(alice)
    session_b = SemaphoreSession(bob)
    resolved = session_a.transmit("urgent: respond immediately", session_b)
    return {
        "synced": synced,
        "token": token,
        "phrase": phrase,
        "semaphore_resolved": resolved,
        "acks": session_b.ledger.acknowledged,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
