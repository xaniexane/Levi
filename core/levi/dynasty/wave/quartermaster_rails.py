# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Quartermaster rails — the 12% cut rail, the fossil store, invoices.

PAPER MONEY ONLY. This module performs no real payment processing:
there are no payment-provider integrations, no bank APIs, no network
calls of any kind — every "collection" is a paper ledger entry under
<home>/dynasty/quartermaster/. Nothing here can move real money, by
design. stdlib only.

Design law, inherited from the Quartermaster:
- Money rails are paper until registered. The only rail named here is
  ``"paper"``.
- The 12% platform cut is enforced IN CODE, fail-closed: every
  collection routes through :meth:`QuartermasterRails.collect`, which
  refuses non-integer, zero, or negative amounts and splits the gross
  with floor arithmetic (remainder to the payee). There is no
  code path that records a gross without the cut.
- Collections are idempotent on the caller's ``transfer_id``: replay
  is refused, never double-counted.
- Fossils are write-once and tamper-evident: the id IS the sha256 of
  the canonical bytes; any byte change breaks the seal.
- Invoices are open until a real cut record links to them; double-pay
  and phantom-invoice pay are refused.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "QuartermasterRails",
    "CutError",
    "FossilError",
    "InvoiceError",
    "PLATFORM_CUT_PERCENT",
    "PAPER_RAIL",
]


class CutError(Exception):
    """A collection was refused or a cut record was inconsistent."""


class FossilError(Exception):
    """A fossil write/verify was refused or tampering was detected."""


class InvoiceError(Exception):
    """An invoice operation was refused."""


#: The platform cut, in percent. Enforced by arithmetic, not policy.
PLATFORM_CUT_PERCENT = 12

#: The only money rail that exists in this build.
PAPER_RAIL = "paper"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_home(home: Optional[Path]) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw) if raw else Path.home() / ".levi"


def _require_cents(value: Any, what: str) -> int:
    """Fail-closed integer-cents validation. bool is not an int here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CutError(f"{what} must be an int of cents, got {type(value).__name__}")
    if value <= 0:
        raise CutError(f"{what} must be positive, got {value}")
    return value


def _require_name(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CutError(f"{what} must be a non-empty string")
    return value.strip()


class QuartermasterRails:
    """Paper money rails: 12% cut enforcement, fossil store, invoices."""

    agent_id = "quartermaster"

    def __init__(self, home: Optional[Path] = None) -> None:
        self._base = _resolve_home(home) / "dynasty" / "quartermaster"
        self._base.mkdir(parents=True, exist_ok=True)
        self._fossils = self._base / "fossils"
        self._fossils.mkdir(parents=True, exist_ok=True)
        self._cuts_path = self._base / "cuts.jsonl"
        self._invoices_path = self._base / "invoices.json"
        self._lock = threading.RLock()
        self._seen_transfer_ids = self._load_seen_transfer_ids()

    # -- 12% cut rail --------------------------------------------------
    def _load_seen_transfer_ids(self) -> set:
        seen: set = set()
        if self._cuts_path.exists():
            try:
                for line in self._cuts_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if isinstance(rec, dict) and isinstance(
                        rec.get("transfer_id"), str
                    ):
                        seen.add(rec["transfer_id"])
            except (OSError, json.JSONDecodeError):
                pass
        return seen

    def collect(
        self,
        amount_cents: int,
        payer: str,
        payee: str,
        memo: str = "",
        *,
        transfer_id: str,
    ) -> Dict[str, Any]:
        """Collect a paper payment, enforcing the 12% platform cut.

        ``platform_cents`` is floor(12% of gross); the payee gets the
        remainder, so no cent is lost or created. ``transfer_id`` is a
        required idempotency key: replaying it raises :class:`CutError`.
        The collection is appended as an immutable JSONL record.
        """
        gross = _require_cents(amount_cents, "amount_cents")
        payer = _require_name(payer, "payer")
        payee = _require_name(payee, "payee")
        if not isinstance(memo, str):
            raise CutError("memo must be a string")
        if not isinstance(transfer_id, str) or not transfer_id.strip():
            raise CutError(
                "transfer_id is required: every collection needs an idempotency key"
            )
        transfer_id = transfer_id.strip()

        platform_cents = (gross * PLATFORM_CUT_PERCENT) // 100  # floor
        payee_cents = gross - platform_cents
        record = {
            "transfer_id": transfer_id,
            "rail": PAPER_RAIL,
            "payer": payer,
            "payee": payee,
            "gross_cents": gross,
            "platform_cents": platform_cents,
            "payee_cents": payee_cents,
            "memo": memo[:200],
            "at": _utcnow(),
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            if transfer_id in self._seen_transfer_ids:
                raise CutError(
                    f"transfer_id {transfer_id!r} already collected — replay refused"
                )
            with self._cuts_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            self._seen_transfer_ids.add(transfer_id)
        return dict(record)

    def cut_record(self, transfer_id: str) -> Dict[str, Any]:
        """Fetch the sealed cut record for a ``transfer_id``."""
        if not isinstance(transfer_id, str) or not transfer_id.strip():
            raise CutError("transfer_id must be a non-empty string")
        transfer_id = transfer_id.strip()
        if self._cuts_path.exists():
            for line in self._cuts_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict) and rec.get("transfer_id") == transfer_id:
                    return rec
        raise CutError(f"no cut record for transfer_id {transfer_id!r}")

    def cut_totals(self) -> Dict[str, int]:
        """Paper totals of sealed cuts — informational only, never money."""
        gross = platform = payee = 0
        with self._lock:
            if self._cuts_path.exists():
                for line in self._cuts_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    gross += int(rec.get("gross_cents", 0))
                    platform += int(rec.get("platform_cents", 0))
                    payee += int(rec.get("payee_cents", 0))
        return {
            "gross_cents": gross,
            "platform_cents": platform,
            "payee_cents": payee,
        }

    # -- fossil store ---------------------------------------------------
    @staticmethod
    def _canonical(kind: str, payload: Dict[str, Any]) -> bytes:
        try:
            return json.dumps(
                {"kind": kind, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise FossilError(
                f"fossil payload is not JSON-serializable: {exc}"
            ) from exc

    @staticmethod
    def _check_id(fossil_id: Any) -> str:
        if (
            not isinstance(fossil_id, str)
            or len(fossil_id) != 64
            or any(c not in "0123456789abcdef" for c in fossil_id)
        ):
            raise FossilError("fossil id must be a 64-char lowercase hex sha256")
        return fossil_id

    def fossilize(self, kind: str, payload: Dict[str, Any]) -> str:
        """Seal a write-once fossil. Returns the fossil id.

        The id is the sha256 of the canonical JSON. Re-sealing the
        same kind+payload returns the same id (idempotent). Finding a
        fossil whose stored bytes differ from what was sealed raises
        :class:`FossilError` — the store is tamper-evident.
        """
        if not isinstance(kind, str) or not kind.strip():
            raise FossilError("fossil kind must be a non-empty string")
        if not isinstance(payload, dict):
            raise FossilError("fossil payload must be a dict")
        kind = kind.strip()
        canonical = self._canonical(kind, payload)
        fossil_id = hashlib.sha256(canonical).hexdigest()
        path = self._fossils / f"{fossil_id}.json"
        record = {
            "id": fossil_id,
            "kind": kind,
            "payload": payload,
            "at": _utcnow(),
        }
        with self._lock:
            if path.exists():
                try:
                    stored = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise FossilError(
                        f"fossil {fossil_id[:12]}… unreadable: {exc}"
                    ) from exc
                if not isinstance(stored, dict):
                    raise FossilError(f"fossil {fossil_id[:12]}… is corrupt")
                resealed = self._canonical(
                    stored.get("kind", ""), stored.get("payload", {})
                )
                if hashlib.sha256(resealed).hexdigest() != fossil_id:
                    raise FossilError(
                        f"fossil {fossil_id[:12]}… tampered: stored bytes "
                        "no longer hash to the id"
                    )
                return fossil_id
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(path)
        return fossil_id

    def read_fossil(self, fossil_id: str) -> Dict[str, Any]:
        """Read a fossil's sealed record. Verifies the seal first."""
        fossil_id = self._check_id(fossil_id)
        path = self._fossils / f"{fossil_id}.json"
        if not path.exists():
            raise FossilError(f"no fossil {fossil_id[:12]}…")
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FossilError(f"fossil {fossil_id[:12]}… unreadable: {exc}") from exc
        if not isinstance(stored, dict):
            raise FossilError(f"fossil {fossil_id[:12]}… is corrupt")
        resealed = self._canonical(stored.get("kind", ""), stored.get("payload", {}))
        if hashlib.sha256(resealed).hexdigest() != fossil_id:
            raise FossilError(
                f"fossil {fossil_id[:12]}… tampered: bytes no longer hash to id"
            )
        return stored

    def verify_fossil(self, fossil_id: str) -> bool:
        """Recompute the fossil's hash. True iff the seal holds."""
        return isinstance(self.read_fossil(fossil_id).get("id"), str)

    def list_fossils(self, kind: Optional[str] = None) -> List[str]:
        """Sorted fossil ids, optionally filtered by kind."""
        ids: List[str] = []
        for path in self._fossils.glob("*.json"):
            stem = path.stem
            if len(stem) != 64:
                continue
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(stored, dict):
                continue
            if kind is not None and stored.get("kind") != kind:
                continue
            ids.append(stem)
        return sorted(ids)

    # -- invoices -------------------------------------------------------
    def _load_invoices(self) -> Dict[str, Dict[str, Any]]:
        if not self._invoices_path.exists():
            return {}
        try:
            data = json.loads(self._invoices_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvoiceError(f"invoice ledger unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise InvoiceError("invoice ledger corrupt")
        return {
            k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, dict)
        }

    def _save_invoices(self, ledger: Dict[str, Dict[str, Any]]) -> None:
        tmp = self._invoices_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._invoices_path)

    def issue_invoice(
        self, payer: str, payee: str, amount_cents: int, memo: str = ""
    ) -> str:
        """Issue an open invoice. Returns the invoice id."""
        amount = _require_cents(amount_cents, "amount_cents")
        payer = _require_name(payer, "payer")
        payee = _require_name(payee, "payee")
        if not isinstance(memo, str):
            raise CutError("memo must be a string")
        invoice_id = "inv-" + uuid.uuid4().hex[:16]
        record = {
            "invoice_id": invoice_id,
            "status": "open",
            "payer": payer,
            "payee": payee,
            "amount_cents": amount,
            "memo": memo[:200],
            "transfer_id": None,
            "at": _utcnow(),
        }
        with self._lock:
            ledger = self._load_invoices()
            ledger[invoice_id] = record
            self._save_invoices(ledger)
        return invoice_id

    def invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Fetch an invoice record; raises if it does not exist."""
        with self._lock:
            ledger = self._load_invoices()
            try:
                return dict(ledger[invoice_id])
            except (KeyError, TypeError) as exc:
                raise InvoiceError(f"no invoice {invoice_id!r}") from exc

    def open_invoices(self) -> List[Dict[str, Any]]:
        """All invoices still open, oldest first."""
        with self._lock:
            ledger = self._load_invoices()
        return [
            dict(rec)
            for rec in sorted(ledger.values(), key=lambda r: r.get("at", ""))
            if rec.get("status") == "open"
        ]

    def pay_invoice(self, invoice_id: str, transfer_id: str) -> Dict[str, Any]:
        """Mark an invoice paid and link the sealed cut record.

        The ``transfer_id`` must name a sealed collection (the 12% cut
        is enforced there). Paying twice, or paying a nonexistent
        invoice, raises :class:`InvoiceError`.
        """
        if not isinstance(transfer_id, str) or not transfer_id.strip():
            raise InvoiceError("pay_invoice requires a transfer_id")
        try:
            cut = self.cut_record(transfer_id.strip())
        except CutError as exc:
            raise InvoiceError(f"pay_invoice refused: {exc}") from exc
        with self._lock:
            ledger = self._load_invoices()
            rec = ledger.get(invoice_id)
            if rec is None:
                raise InvoiceError(f"no invoice {invoice_id!r}")
            if rec.get("status") != "open":
                raise InvoiceError(f"invoice {invoice_id!r} is already paid")
            rec["status"] = "paid"
            rec["transfer_id"] = cut["transfer_id"]
            rec["paid_at"] = _utcnow()
            self._save_invoices(ledger)
            return dict(rec)
