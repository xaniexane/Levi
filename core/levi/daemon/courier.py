"""Courier — sealed-envelope carrier between organs and seats.

LEVI's organs (Echo, Mandella, REIM, RIEM, Hatter) and crew seats need to
hand each other work without trusting the filesystem blindly. The courier
moves sealed envelopes: each envelope carries a sha256 checksum over its
canonical payload, so tampering in transit is detectable.

Flow: ``seal()`` → ``send()`` (outbox) → ``tick()`` delivers each
envelope to the recipient's inbox and writes a delivery receipt. A
corrupted envelope is quarantined to ``dead/`` with a tamper receipt —
never delivered, never silently dropped.

The courier is transport, not policy: it does not judge payloads, it
only guarantees honest carriage. Every delivery also publishes a
``courier.delivered`` signal on the bus (``courier.tampered`` for
quarantines).

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.courier`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.daemon.signalbus import SignalBus

DEFAULT_STATE_DIR = Path.home() / ".levi" / "courier"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _seal(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class Envelope:
    """A sealed message from one organ/seat to another."""

    id: str
    sender: str
    recipient: str
    payload: Dict[str, Any] = field(default_factory=dict)
    sealed_at: str = ""
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Envelope":
        return Envelope(
            id=str(data["id"]),
            sender=str(data["sender"]),
            recipient=str(data["recipient"]),
            payload=dict(data.get("payload") or {}),
            sealed_at=str(data.get("sealed_at", "")),
            checksum=str(data.get("checksum", "")),
        )

    def verify(self) -> bool:
        return bool(self.checksum) and self.checksum == _seal(self.payload)


@dataclass
class DeliveryReceipt:
    envelope_id: str
    sender: str
    recipient: str
    delivered_at: str
    tampered: bool = False
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CourierReport:
    """Outcome of one courier tick."""

    at: str = ""
    delivered: List[str] = field(default_factory=list)
    quarantined: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Courier:
    """Honest carriage for sealed inter-organ envelopes."""

    def __init__(
        self,
        home: Optional[Path] = None,
        journal_path: Optional[Path] = None,
    ) -> None:
        self.home = Path(home) if home is not None else Path.home()
        self.state_dir = self.home / ".levi" / "courier"
        self.outbox = self.state_dir / "outbox"
        self.inbox = self.state_dir / "inbox"
        self.receipts = self.state_dir / "receipts"
        self.dead = self.state_dir / "dead"
        bus_journal = (
            Path(journal_path)
            if journal_path
            else self.home / ".levi" / "daemon_signalbus.jsonl"
        )
        self.bus = SignalBus(journal_path=bus_journal)

    # -- sealing / sending ------------------------------------------------

    def seal(self, sender: str, recipient: str, payload: Dict[str, Any]) -> Envelope:
        """Create a sealed envelope. Raises ValueError on bad input."""
        if not sender or not isinstance(sender, str):
            raise ValueError("seal: 'sender' must be a non-empty string")
        if not recipient or not isinstance(recipient, str):
            raise ValueError("seal: 'recipient' must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError(
                f"seal: 'payload' must be a dict, got {type(payload).__name__}"
            )
        env = Envelope(
            id=hashlib.sha256(
                f"{sender}:{recipient}:{_utcnow_iso()}:{_canonical(payload)}".encode(
                    "utf-8"
                )
            ).hexdigest()[:16],
            sender=sender,
            recipient=recipient,
            payload=dict(payload),
            sealed_at=_utcnow_iso(),
        )
        env.checksum = _seal(env.payload)
        return env

    def send(self, envelope: Envelope) -> Path:
        """Drop a sealed envelope in the outbox."""
        if not envelope.verify():
            raise ValueError("send: envelope checksum invalid — refusing to carry")
        path = self.outbox / f"{envelope.id}.json"
        _atomic_write(path, json.dumps(envelope.to_dict(), indent=2))
        return path

    # -- delivery ----------------------------------------------------------

    def _write_receipt(self, receipt: DeliveryReceipt) -> None:
        _atomic_write(
            self.receipts / f"{receipt.envelope_id}.json",
            json.dumps(receipt.to_dict(), indent=2),
        )

    def _deliver_one(self, path: Path, report: CourierReport) -> None:
        try:
            envelope = Envelope.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report.errors.append(f"unreadable envelope {path.name}: {exc}")
            return
        if not envelope.verify():
            # Tampered: quarantine, receipt, alert. Never deliver.
            try:
                self.dead.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(self.dead / path.name))
            except OSError as exc:
                report.errors.append(f"quarantine failed for {path.name}: {exc}")
                return
            receipt = DeliveryReceipt(
                envelope_id=envelope.id,
                sender=envelope.sender,
                recipient=envelope.recipient,
                delivered_at=_utcnow_iso(),
                tampered=True,
                note="checksum mismatch — quarantined, NOT delivered",
            )
            self._write_receipt(receipt)
            report.quarantined.append(envelope.id)
            try:
                self.bus.publish(
                    "courier.tampered", receipt.to_dict(), publisher="courier"
                )
            except Exception:  # noqa: BLE001
                pass
            return
        dest_dir = self.inbox / envelope.recipient
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(path), str(dest_dir / path.name))
        except OSError as exc:
            report.errors.append(f"delivery failed for {envelope.id}: {exc}")
            return
        receipt = DeliveryReceipt(
            envelope_id=envelope.id,
            sender=envelope.sender,
            recipient=envelope.recipient,
            delivered_at=_utcnow_iso(),
            note="delivered intact",
        )
        self._write_receipt(receipt)
        report.delivered.append(envelope.id)
        try:
            self.bus.publish(
                "courier.delivered", receipt.to_dict(), publisher="courier"
            )
        except Exception:  # noqa: BLE001
            pass

    def tick(self) -> CourierReport:
        """Deliver everything waiting in the outbox. Never raises."""
        report = CourierReport(at=_utcnow_iso())
        if not self.outbox.is_dir():
            return report
        for path in sorted(self.outbox.glob("*.json")):
            try:
                self._deliver_one(path, report)
            except Exception as exc:  # noqa: BLE001 — one bad file can't stop us
                report.errors.append(f"delivery crashed on {path.name}: {exc}")
        return report

    def collect(self, recipient: str, clear: bool = True) -> List[Envelope]:
        """Pick up delivered envelopes for one organ/seat."""
        box = self.inbox / recipient
        envelopes: List[Envelope] = []
        if not box.is_dir():
            return envelopes
        for path in sorted(box.glob("*.json")):
            try:
                envelopes.append(
                    Envelope.from_dict(json.loads(path.read_text(encoding="utf-8")))
                )
                if clear:
                    path.unlink()
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return envelopes

    def check(self) -> tuple:
        """Lightweight coherence check for the supervisor (never raises)."""
        try:
            waiting = (
                len(list(self.outbox.glob("*.json"))) if self.outbox.is_dir() else 0
            )
            receipts = (
                len(list(self.receipts.glob("*.json"))) if self.receipts.is_dir() else 0
            )
            dead = len(list(self.dead.glob("*.json"))) if self.dead.is_dir() else 0
            return True, (
                f"outbox={waiting} delivered_receipts={receipts} quarantined={dead}"
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"courier check failed: {exc}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.courier")
    ap.parse_args(argv)
    report = Courier().tick()
    print(
        "courier tick: delivered=%d quarantined=%d"
        % (len(report.delivered), len(report.quarantined))
    )
    for eid in report.delivered:
        print(f"  delivered:   {eid}")
    for eid in report.quarantined:
        print(f"  QUARANTINED: {eid}")
    for err in report.errors:
        print(f"  error:       {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
