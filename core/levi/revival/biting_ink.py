"""LEVI's biting ink: provenance that etches deeper the longer it sits.

Studied from: lost-crafts-20260916/report.md [Batch 3] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a mark should *bite* into its medium —
grow harder to dispute with time, not easier. The ``InkLedger`` is a
hash-chained record: each entry seals the previous entry's seal together
with its own payload digest, so altering any record breaks every seal after
it. The *bite* is the entry's depth behind the chain tip: as new entries pile
on, an old record's ``bite_strength`` grows — the seal corrodes/strengthens
with time, in the ledger's favor. ``verify()`` replays the chain and names
the first broken link.

Honesty: tamper-*evidence*, not tamper-*proof*. The ledger detects edits and
reordering after the fact; it cannot stop someone with write access from
rewriting the whole chain from scratch. The bite makes quiet edits to old
records expensive to hide, not impossible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

ORIGIN = "levi-revival/biting-ink"


def _seal(prev_seal: str, payload_digest: str) -> str:
    return hashlib.sha256(f"{prev_seal}|{payload_digest}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InkEntry:
    """One etched record: index, payload, and the seal binding it to history."""

    index: int
    payload: str
    payload_digest: str
    prev_seal: str
    seal: str


class InkLedger:
    """An append-only hash-chained ledger with time-strengthening seals."""

    GENESIS_SEAL = "GENESIS"

    def __init__(self) -> None:
        self._entries: List[InkEntry] = []

    # -- writing ------------------------------------------------------------------
    def etch(self, payload: str) -> InkEntry:
        """Append a record. Returns the sealed entry."""
        if not isinstance(payload, str):
            raise TypeError("payload must be a string")
        prev = self._entries[-1].seal if self._entries else self.GENESIS_SEAL
        payload_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        entry = InkEntry(
            index=len(self._entries),
            payload=payload,
            payload_digest=payload_digest,
            prev_seal=prev,
            seal=_seal(prev, payload_digest),
        )
        self._entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def entry(self, index: int) -> InkEntry:
        return self._entries[index]

    # -- the bite -------------------------------------------------------------------
    def bite_strength(self, index: int) -> int:
        """How deep the mark has bitten: entries piled on top of it.

        A fresh entry has strength 0; every later entry deepens the bite by
        one. Old records are the hardest to quietly alter.
        """
        if not 0 <= index < len(self._entries):
            raise IndexError("entry index out of range")
        return len(self._entries) - 1 - index

    # -- verification -----------------------------------------------------------------
    def verify(self) -> Tuple[bool, Optional[int]]:
        """Replay the chain. Returns (True, None) or (False, first_bad_index)."""
        prev = self.GENESIS_SEAL
        for i, e in enumerate(self._entries):
            want_payload = hashlib.sha256(e.payload.encode("utf-8")).hexdigest()
            if e.payload_digest != want_payload:
                return False, i
            if e.prev_seal != prev:
                return False, i
            if e.seal != _seal(e.prev_seal, e.payload_digest):
                return False, i
            prev = e.seal
        return True, None

    def etch_report(self) -> List[Tuple[int, str, int]]:
        """(index, seal prefix, bite strength) for every entry, oldest first."""
        return [
            (e.index, e.seal[:12], self.bite_strength(e.index)) for e in self._entries
        ]
