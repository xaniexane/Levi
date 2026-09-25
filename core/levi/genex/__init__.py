"""GenEX — the immutable asset ledger (Execution Layer organ).

Canon: GenEX is the immutable asset ledger of the SER architecture,
attested in the founder corpus alongside SupraStreet (commerce), Eden
(experiments), Vector (sandbox), and the Execution Layer table. It was
revived as docs-level only in the dead-software inventory (§16) and
confirmed still absent from the tree by the 2026-09-22 hunt audit.

This is the LEVI-native organ built from scratch — never a copy of
anything. It is NOT the free-tier metering ledger
(:mod:`core.levi.catalogue.ledger`) and NOT the dynasty-NFT ledger
(:mod:`core.levi.genesis.nft.ledger`); those are different concepts.

Public surface: :class:`GenexLedger` — ``issue``, ``transfer``,
``retire``, ``balance``, ``total_supply``, ``history``, ``verify_chain``.

Law (declared up front; tests are the proof):
1. APPEND-ONLY — entries are never updated or deleted. No such method
   exists.
2. HASH CHAIN — every entry carries ``prev_hash`` and its own
   ``sha256``; :meth:`verify_chain` re-hashes and re-links everything.
   Any tamper fails verification.
3. CONSERVATION — per asset, sum of balances == total issued minus
   retired. Minting happens only through ``issue``; destruction only
   through ``retire``; both are chain-recorded operations.
4. DETERMINISM — the same operation sequence always yields the same
   hashes (canonical JSON serialization).
"""

from .ledger import GenexLedger

__all__ = ["GenexLedger"]
