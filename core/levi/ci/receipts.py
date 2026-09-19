"""Hash-chained verdict receipts — the counsels' proof of judgment.

Every counsel verdict is receipted on a CI-local chain kept under
``<home>/ci/receipts/`` (``<home>`` from ``LEVI_HOME``, else ``~/.levi``).
The discipline mirrors the dynasty's: a receipt is a canonical JSON
record carrying a sequence number, a link to the previous receipt's hash
(``GENESIS`` for the first), and a SHA-256 of its own canonical body.
``verify_chain`` re-walks every receipt — recomputed body hash, unbroken
linkage. A tampered byte raises :exc:`ReceiptError`.

The chain is CI-local on purpose: the dynasty's keeper-key-sealed receipt
machinery is Section-0 apparatus and is not borrowed. Counsel receipts
prove judgment, not dynasty work.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_GENESIS = "GENESIS"

_MINT_LOCK = threading.Lock()


class ReceiptError(ValueError):
    """A verdict receipt's hash or the chain linkage is broken."""


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def receipts_dir() -> Path:
    d = _home() / "ci" / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _body_hash(body: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _existing() -> list[Path]:
    d = receipts_dir()
    files = [p for p in d.glob("verdict-*.json")]
    def seq(p: Path) -> int:
        try:
            return int(p.stem.split("-")[1])
        except (IndexError, ValueError):
            return -1
    return sorted(files, key=seq)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def mint_verdict_receipt(verdict_body: Dict[str, Any]) -> Dict[str, Any]:
    """Mint a hash-chained receipt for one counsel verdict."""
    with _MINT_LOCK:
        existing = _existing()
        seq = len(existing) + 1
        prev_hash = _GENESIS if not existing else _load(existing[-1])["body_hash"]
        body = {
            "verdict_id": verdict_body["verdict_id"],
            "counsel": verdict_body["counsel"],
            "minion_id": verdict_body["minion_id"],
            "minion_class": verdict_body["minion_class"],
            "case_fingerprint": verdict_body["case_fingerprint"],
            "ruling": verdict_body["ruling"],
            "ts": verdict_body.get("ts")
            or datetime.now(timezone.utc).isoformat(),
        }
        receipt = {
            "seq": seq,
            "prev_hash": prev_hash,
            "body": body,
            "body_hash": _body_hash({"seq": seq, "prev_hash": prev_hash, "body": body}),
            "minted_ts": datetime.now(timezone.utc).isoformat(),
        }
        path = receipts_dir() / f"verdict-{seq:06d}.json"
        # O_EXCL: a receipt, once minted, is never overwritten.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(receipt, indent=2, sort_keys=True))
        return receipt


def verify_chain() -> int:
    """Re-walk the chain. Returns the receipt count; raises on any break."""
    prev_hash = _GENESIS
    count = 0
    for path in _existing():
        receipt = _load(path)
        count += 1
        if receipt["seq"] != count:
            raise ReceiptError(f"sequence break at {path.name}")
        if receipt["prev_hash"] != prev_hash:
            raise ReceiptError(f"linkage break at {path.name}")
        recomputed = _body_hash(
            {"seq": receipt["seq"], "prev_hash": receipt["prev_hash"],
             "body": receipt["body"]}
        )
        if recomputed != receipt["body_hash"]:
            raise ReceiptError(f"body hash mismatch at {path.name}")
        prev_hash = receipt["body_hash"]
    return count
