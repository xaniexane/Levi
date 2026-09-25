"""GenEX immutable asset ledger: hash-chained, append-only.

An asset is identified by ``asset_id`` (a string). Holders are arbitrary
string identities. Amounts are integers in the asset's smallest unit —
no floats, so conservation is exact.

Operations, all recorded as chain entries:
- ``issue(asset_id, to, amount, memo)`` — mint new units.
- ``transfer(asset_id, from_, to, amount, memo)`` — move units.
- ``retire(asset_id, from_, amount, memo)`` — destroy units.

Every entry: ``{"seq", "op", "asset_id", "from", "to", "amount",
"memo", "at", "prev_hash", "hash"}``. ``hash`` is sha256 over the
canonical (sorted-key, compact-separator) JSON of the entry minus
``hash`` itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


_GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    op: str
    asset_id: str
    from_: str
    to: str
    amount: int
    memo: str
    at: str
    prev_hash: str
    hash: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "op": self.op,
            "asset_id": self.asset_id,
            "from": self.from_,
            "to": self.to,
            "amount": self.amount,
            "memo": self.memo,
            "at": self.at,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


class GenexError(ValueError):
    """Any refusal: invalid amount, insufficient balance, bad identity."""


class GenexLedger:
    """Append-only, hash-chained asset ledger."""

    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []
        self._balances: Dict[str, Dict[str, int]] = {}
        self._issued: Dict[str, int] = {}
        self._retired: Dict[str, int] = {}
        self._seq = 0

    # -- internals -----------------------------------------------------
    @staticmethod
    def _check_amount(amount: int) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise GenexError("amount must be a positive integer")

    @staticmethod
    def _check_id(value: str, what: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise GenexError(f"{what} must be a non-empty string")

    def _append(self, op: str, asset_id: str, from_: str, to: str,
                amount: int, memo: str, at: str) -> LedgerEntry:
        prev = self._entries[-1].hash if self._entries else _GENESIS_HASH
        body = {
            "seq": self._seq,
            "op": op,
            "asset_id": asset_id,
            "from": from_,
            "to": to,
            "amount": amount,
            "memo": memo or "",
            "at": at or "",
            "prev_hash": prev,
        }
        entry = LedgerEntry(
            hash=_hash(body),
            seq=body["seq"],
            op=body["op"],
            asset_id=body["asset_id"],
            from_=body["from"],
            to=body["to"],
            amount=body["amount"],
            memo=body["memo"],
            at=body["at"],
            prev_hash=body["prev_hash"],
        )
        self._entries.append(entry)
        self._seq += 1
        return entry

    def _add_balance(self, asset_id: str, holder: str, delta: int) -> None:
        book = self._balances.setdefault(asset_id, {})
        book[holder] = book.get(holder, 0) + delta

    # -- operations ----------------------------------------------------
    def issue(self, asset_id: str, to: str, amount: int,
              memo: str = "", at: str = "") -> LedgerEntry:
        """Mint new units of an asset to a holder (chain-recorded)."""
        self._check_id(asset_id, "asset_id")
        self._check_id(to, "holder")
        self._check_amount(amount)
        entry = self._append("issue", asset_id, "", to, amount, memo, at)
        self._add_balance(asset_id, to, amount)
        self._issued[asset_id] = self._issued.get(asset_id, 0) + amount
        return entry

    def transfer(self, asset_id: str, from_: str, to: str, amount: int,
                 memo: str = "", at: str = "") -> LedgerEntry:
        """Move units between holders; refuses on insufficient balance."""
        # MONEY LAW: in-memory hash-chained asset ledger. Moves integer unit
        # counters between string identities; no currency, no network, no
        # payout path. Any future real-asset rail routes via
        # levi.cybrus.money.MoneyGateway.
        self._check_id(asset_id, "asset_id")
        self._check_id(from_, "sender")
        self._check_id(to, "recipient")
        self._check_amount(amount)
        if self.balance(asset_id, from_) < amount:
            raise GenexError(
                f"insufficient balance: {from_} holds "
                f"{self.balance(asset_id, from_)} of {asset_id}"
            )
        entry = self._append("transfer", asset_id, from_, to, amount, memo, at)
        self._add_balance(asset_id, from_, -amount)
        self._add_balance(asset_id, to, amount)
        return entry

    def retire(self, asset_id: str, from_: str, amount: int,
               memo: str = "", at: str = "") -> LedgerEntry:
        """Destroy units held by a holder (chain-recorded)."""
        self._check_id(asset_id, "asset_id")
        self._check_id(from_, "holder")
        self._check_amount(amount)
        if self.balance(asset_id, from_) < amount:
            raise GenexError(
                f"insufficient balance: {from_} holds "
                f"{self.balance(asset_id, from_)} of {asset_id}"
            )
        entry = self._append("retire", asset_id, from_, "", amount, memo, at)
        self._add_balance(asset_id, from_, -amount)
        self._retired[asset_id] = self._retired.get(asset_id, 0) + amount
        return entry

    # -- reads ---------------------------------------------------------
    def balance(self, asset_id: str, holder: str) -> int:
        return self._balances.get(asset_id, {}).get(holder, 0)

    def total_supply(self, asset_id: str) -> int:
        """Issued minus retired — the conservation anchor."""
        return self._issued.get(asset_id, 0) - self._retired.get(asset_id, 0)

    def holders(self, asset_id: str) -> Dict[str, int]:
        return dict(self._balances.get(asset_id, {}))

    def history(self, asset_id: str | None = None) -> List[Dict[str, Any]]:
        entries = self._entries
        if asset_id is not None:
            entries = [e for e in entries if e.asset_id == asset_id]
        return [e.as_dict() for e in entries]

    def verify_chain(self) -> Dict[str, Any]:
        """Re-hash and re-link every entry. Returns ok + first failure."""
        prev = _GENESIS_HASH
        for entry in self._entries:
            body = entry.as_dict()
            digest = body.pop("hash")
            if body["prev_hash"] != prev:
                return {"ok": False, "seq": entry.seq,
                        "reason": "prev_hash link broken"}
            if _hash(body) != digest:
                return {"ok": False, "seq": entry.seq,
                        "reason": "entry hash mismatch (tampered)"}
            prev = digest
        return {"ok": True, "entries": len(self._entries)}
