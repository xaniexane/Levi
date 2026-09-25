"""The Zunftlade: the guild chest as multi-key institutional memory.

Origin: the guild chest held the charter, the seal, the registers of
apprentices and masters, masterpiece drawings, fines ledgers, and
mutual-aid funds — often under multiple locks with different
key-holders, so opening it required a quorum. No single officer could
alter the record alone: distributed custody was tamper resistance. And
the apprenticeship registers made skill lineage auditable — any
master's training chain could be traced back through the books.

What it is in LEVI: ``MultiKeyChest`` — records that require K-of-N
officer signatures to amend (an amendment without quorum is refused),
plus lineage entries that trace training chains: who trained whom, all
the way back. Tamper resistance and auditable lineage in one chest.

Honesty label: LOAD-BEARING — quorum-gated amendment + lineage
chain-walking is a concrete, transferable mechanism.

Deny-closed inputs: empty officer / record / person names, a quorum
below 2, duplicate officers, duplicate records, unknown record or
officer ids, the same officer signing an amendment twice, ratifying
without quorum, and tracing lineage for an unknown person are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Record", "MultiKeyChest"]


@dataclass
class Record:
    id: str
    content: str
    amendments: int = 0


class MultiKeyChest:
    """Institutional memory under distributed custody: no single officer
    can alter a record alone, and every training chain stays auditable."""

    def __init__(self, quorum: int):
        if not isinstance(quorum, int) or isinstance(quorum, bool):
            raise ValueError("quorum must be an integer")
        if quorum < 2:
            raise ValueError("quorum must be at least 2 (multi-key custody)")
        self.quorum = quorum
        self._officers: dict[str, str] = {}  # officer id -> name
        self._records: dict[str, Record] = {}
        # record id -> proposed content -> set of signing officer ids
        self._pending: dict[str, tuple[str, set[str]]] = {}
        # apprentice name -> master name (the lineage register)
        self._lineage: dict[str, str] = {}
        self._counter = 0

    # -- the officers ------------------------------------------------------------
    def add_officer(self, name: str) -> str:
        """Seat a key-holder of the chest."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("officer name must be a non-empty string")
        name = name.strip()
        if any(n.lower() == name.lower() for n in self._officers.values()):
            raise ValueError(f"duplicate officer: {name!r}")
        self._counter += 1
        officer_id = f"officer-{self._counter}"
        self._officers[officer_id] = name
        return officer_id

    # -- the chest ------------------------------------------------------------------
    def file_record(self, record_id: str, content: str) -> Record:
        """Place an original record in the chest."""
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record id must be a non-empty string")
        record_id = record_id.strip()
        if record_id in self._records:
            raise ValueError(f"duplicate record: {record_id!r}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("record content must be a non-empty string")
        record = Record(id=record_id, content=content.strip())
        self._records[record_id] = record
        return record

    def propose_amendment(
        self, record_id: str, new_content: str, officer_id: str
    ) -> int:
        """An officer signs an amendment proposal. Returns the signature
        count so far; the amendment applies only at quorum."""
        record = self._records.get(record_id)
        if record is None:
            raise ValueError(f"unknown record: {record_id!r}")
        if officer_id not in self._officers:
            raise ValueError(f"unknown officer: {officer_id!r}")
        if not isinstance(new_content, str) or not new_content.strip():
            raise ValueError("amendment content must be a non-empty string")
        existing = self._pending.get(record_id)
        if existing is not None and existing[0] != new_content.strip():
            raise ValueError(
                f"a different amendment is already pending for {record_id!r}"
            )
        signers = existing[1] if existing else set()
        if officer_id in signers:
            raise ValueError(f"officer {officer_id!r} already signed this amendment")
        signers.add(officer_id)
        self._pending[record_id] = (new_content.strip(), signers)
        return len(signers)

    def ratify(self, record_id: str) -> Record:
        """Apply the pending amendment — only with a quorum of distinct
        officer signatures. Without quorum the chest stays shut."""
        record = self._records.get(record_id)
        if record is None:
            raise ValueError(f"unknown record: {record_id!r}")
        pending = self._pending.get(record_id)
        if pending is None:
            raise ValueError(f"no amendment pending for {record_id!r}")
        new_content, signers = pending
        if len(signers) < self.quorum:
            raise ValueError(
                f"quorum not met: {len(signers)} signatures, {self.quorum} required"
            )
        record.content = new_content
        record.amendments += 1
        del self._pending[record_id]
        return record

    # -- the lineage register ----------------------------------------------------------
    def register_training(self, apprentice: str, master: str) -> None:
        """Enter one link of the training chain: who trained whom."""
        for label, value in (("apprentice", apprentice), ("master", master)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be a non-empty string")
        apprentice, master = apprentice.strip(), master.strip()
        if apprentice.lower() == master.lower():
            raise ValueError("apprentice and master must differ")
        self._lineage[apprentice] = master

    def lineage(self, person: str) -> list[str]:
        """Walk the training chain back: person, their master, their
        master's master, to the root of the books."""
        if not isinstance(person, str) or not person.strip():
            raise ValueError("person must be a non-empty string")
        person = person.strip()
        if person not in self._lineage and not any(
            m.lower() == person.lower() for m in self._lineage.values()
        ):
            raise ValueError(f"unknown person in the register: {person!r}")
        chain = [person]
        seen = {person.lower()}
        while chain[-1] in self._lineage:
            nxt = self._lineage[chain[-1]]
            if nxt.lower() in seen:
                raise ValueError(f"lineage cycle detected at {nxt!r}")
            chain.append(nxt)
            seen.add(nxt.lower())
        return chain

    def chest_summary(self) -> dict:
        return {
            "officers": len(self._officers),
            "quorum": self.quorum,
            "records": len(self._records),
            "pending_amendments": len(self._pending),
            "lineage_entries": len(self._lineage),
        }
