# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Sealed, hash-chained task receipts — the dynasty's proof of work.

Every task runs plan→execute→verify→receipt. A receipt is a canonical
JSON record carrying a sequence number, a link to the previous
receipt's hash (``GENESIS`` for the first), a SHA-256 of its own
canonical body, and an HMAC-SHA256 seal minted with the keeper key.

The keeper key (32 bytes) is created once at
``<home>/dynasty/keeper.key`` (mode 0o600) and never leaves that file.
``<home>`` resolves from the ``LEVI_HOME`` env var, falling back to
``~/.levi``. Receipt files are created with O_EXCL — a receipt, once
minted, is never overwritten.

:func:`verify_chain` re-walks every receipt: recomputed body hash,
recomputed MAC, unbroken linkage. A single tampered byte raises
:exc:`ReceiptError`. Receipts are never repaired in place; a break is
reported, loudly, and the chain is forked or re-seeded under a new
genesis.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_GENESIS = "GENESIS"

#: Process-wide mint lock: the mint is read-then-write (seq = len+1,
#: O_EXCL file). Without the lock, two threads minting in the same
#: second compute the same name and the loser eats a raw
#: FileExistsError — or worse, a forked sequence. (Purge: F-SW-1.)
_MINT_LOCK = threading.Lock()

#: Process-wide keeper-key lock: first-boot key birth is atomic and
#: single-flight. (Purge: F-SW-2.)
_KEY_LOCK = threading.Lock()


class ReceiptError(ValueError):
    """A receipt's seal or the chain linkage is broken."""


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _dynasty_dir() -> Path:
    d = _home() / "dynasty"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _receipts_dir() -> Path:
    d = _dynasty_dir() / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _keeper_key() -> bytes:
    # Single-flight, atomic birth: the key file is created via
    # temp-file + rename, so no thread ever reads a partially-written
    # key and forks its key view (which breaks the chain permanently).
    # A lost creation race re-reads the winner's file instead of
    # raising FileExistsError.
    with _KEY_LOCK:
        key_path = _dynasty_dir() / "keeper.key"
        if not key_path.exists():
            import secrets

            tmp_path = key_path.with_suffix(".tmp")
            fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(secrets.token_bytes(32))
                try:
                    os.replace(tmp_path, key_path)
                except OSError:
                    # lost the race after writing temp: winner's key stands
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        else:
            os.chmod(key_path, 0o600)
        data = key_path.read_bytes()
    if len(data) != 32:
        raise ReceiptError("keeper key is not 32 bytes — refusing to mint")
    return data


def _canonical(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_receipts() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(_receipts_dir().glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            # ValueError covers JSONDecodeError AND UnicodeDecodeError:
            # a byte-flipped receipt file must raise the documented
            # ReceiptError, never leak a raw codec error. (F-WC-1.)
            raise ReceiptError(f"unreadable receipt file: {path.name}") from None
    out.sort(key=lambda r: r.get("seq", 0))
    return out


def mint_receipt(kind: str, payload: Dict[str, Any], task: str = "") -> Dict[str, Any]:
    """Mint a sealed receipt for a completed, verified task.

    Chains onto the previous receipt (``GENESIS`` for the first).
    The whole mint holds the process-wide mint lock, and a lost
    O_EXCL race (cross-process, same-second identical body) retries
    with jitter — the loser re-reads the advanced sequence instead of
    crashing. Returns the full receipt dict, including
    ``receipt_hash`` and ``mac``.
    """
    if not kind or not kind.strip():
        raise ReceiptError("kind must be non-empty")
    last_exc: Optional[Exception] = None
    for attempt in range(16):
        try:
            with _MINT_LOCK:
                return _mint_once(kind.strip(), payload, task)
        except FileExistsError as exc:
            last_exc = exc
            time.sleep(0.001 * (attempt + 1))
    raise ReceiptError(f"receipt mint lost too many races: {last_exc}")


def _mint_once(kind: str, payload: Dict[str, Any], task: str) -> Dict[str, Any]:
    receipts = _read_receipts()
    seq = len(receipts) + 1
    prev_hash = receipts[-1]["receipt_hash"] if receipts else _GENESIS
    body: Dict[str, Any] = {
        "kind": kind,
        "task": task,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seq": seq,
        "prev_hash": prev_hash,
    }
    receipt_hash = hashlib.sha256(_canonical(body)).hexdigest()
    mac = hmac.new(
        _keeper_key(), receipt_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    receipt = dict(body)
    receipt["receipt_hash"] = receipt_hash
    receipt["mac"] = mac
    path = _receipts_dir() / f"{receipt_hash[:16]}.json"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_canonical(receipt).decode("utf-8"))
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return receipt


def verify_chain() -> int:
    """Re-verify every receipt's hash, MAC, and linkage.

    Returns the number of verified receipts. Raises
    :exc:`ReceiptError` on the first break found.
    """
    receipts = _read_receipts()
    keeper = _keeper_key()
    expected_prev = _GENESIS
    for i, receipt in enumerate(receipts):
        try:
            body = {
                k: receipt[k]
                for k in ("kind", "task", "payload", "created_at", "seq", "prev_hash")
            }
        except KeyError as exc:
            raise ReceiptError(f"receipt {i + 1}: missing field {exc}") from exc
        if receipt.get("seq") != i + 1:
            raise ReceiptError(
                f"receipt {i + 1}: out-of-order sequence {receipt.get('seq')!r}"
            )
        recomputed = hashlib.sha256(_canonical(body)).hexdigest()
        if recomputed != receipt.get("receipt_hash"):
            raise ReceiptError(f"receipt {i + 1}: body hash mismatch — tampered")
        expected_mac = hmac.new(
            keeper, receipt["receipt_hash"].encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_mac, receipt.get("mac", "")):
            raise ReceiptError(
                f"receipt {i + 1}: MAC mismatch — not minted by this keeper"
            )
        if receipt.get("prev_hash") != expected_prev:
            raise ReceiptError(f"receipt {i + 1}: linkage break — prev_hash mismatch")
        expected_prev = receipt["receipt_hash"]
    return len(receipts)
