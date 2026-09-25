"""True-delete ephemeral channels: local encrypted store with TTL and proofs.

A channel is a folder on your disk. Each message body is encrypted at
rest (see :mod:`levi.ephemera.crypto` for the honest crypto note), carries
a per-channel TTL, and when it expires :meth:`EphemeraStore.sweep`
secure-overwrites the record file (random passes + zeros) before deleting
it, then appends a deletion receipt to a hash-chained log — a receipt you
can verify to prove *to yourself* the deletion happened, with no cloud
retention backdoor because there is no cloud at all.

Screenshot honesty: this module cannot stop a reader from screenshotting.
It does not pretend to. Instead every message can carry a
``forwarding_discouraged`` flag (an explicit social contract, shown on
read), and every read is appended to an access log the channel owner can
inspect.

All home paths resolve at call time (see :func:`ephemera_home`) so tests
can point HOME at a tmp dir.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.ephemera.crypto import (
    chain_hash,
    derive_key,
    new_salt,
    open_seal,
    seal,
)

ENC = "utf-8"
GENESIS = b"\x00" * 32
_OVERWRITE_PASSES = 3


def ephemera_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "ephemera"


class EphemeraError(Exception):
    pass


def _now() -> float:
    return time.time()


class EphemeraStore:
    """Local ephemeral-channel store rooted at ``ephemera_home(home)``."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.root = ephemera_home(home)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- channels -----------------------------------------------------------
    def _chan_dir(self, channel: str) -> Path:
        return self.root / "channels" / channel

    def create_channel(
        self, name: str, ttl_seconds: int, passphrase: str
    ) -> Dict[str, Any]:
        if not name or "/" in name or name.startswith("."):
            raise EphemeraError("bad channel name")
        if ttl_seconds < 0:
            raise EphemeraError("ttl must be >= 0")
        d = self._chan_dir(name)
        if (d / "channel.json").exists():
            raise EphemeraError("channel already exists: %s" % name)
        d.mkdir(parents=True)
        salt = new_salt()
        manifest = {
            "name": name,
            "ttl_seconds": ttl_seconds,
            "created_at": _now(),
            "salt_hex": salt.hex(),
            "kdf": "pbkdf2-hmac-sha256/210k",
        }
        (d / "channel.json").write_text(json.dumps(manifest, indent=2), encoding=ENC)
        return manifest

    def _load_manifest(self, channel: str) -> Dict[str, Any]:
        p = self._chan_dir(channel) / "channel.json"
        if not p.exists():
            raise EphemeraError("unknown channel: %s" % channel)
        return json.loads(p.read_text(encoding=ENC))

    def _channel_key(self, manifest: Dict[str, Any], passphrase: str) -> bytes:
        return derive_key(passphrase.encode(ENC), bytes.fromhex(manifest["salt_hex"]))

    def list_channels(self) -> List[str]:
        chandir = self.root / "channels"
        if not chandir.exists():
            return []
        return sorted(
            p.name for p in chandir.iterdir() if (p / "channel.json").exists()
        )

    # -- messages -----------------------------------------------------------
    def post(
        self,
        channel: str,
        author: str,
        body: str,
        passphrase: str,
        forwarding_discouraged: bool = False,
        ttl_override: "int | None" = None,
    ) -> Dict[str, Any]:
        manifest = self._load_manifest(channel)
        ttl = manifest["ttl_seconds"] if ttl_override is None else ttl_override
        key = self._channel_key(manifest, passphrase)
        msg_id = uuid.uuid4().hex[:16]
        created = _now()
        blob = seal(key, body.encode(ENC))
        record = {
            "id": msg_id,
            "author": author,
            "created_at": created,
            "expires_at": created + ttl,
            "ttl_seconds": ttl,
            "forwarding_discouraged": bool(forwarding_discouraged),
            "blob_hex": blob.hex(),
        }
        path = self._chan_dir(channel) / ("msg_%s.json" % msg_id)
        path.write_text(json.dumps(record), encoding=ENC)
        return {"id": msg_id, "expires_at": record["expires_at"]}

    def _iter_records(self, channel: str):
        d = self._chan_dir(channel)
        for p in sorted(d.glob("msg_*.json")):
            yield p, json.loads(p.read_text(encoding=ENC))

    def read_message(
        self, channel: str, msg_id: str, passphrase: str, reader: str = "owner"
    ) -> Dict[str, Any]:
        manifest = self._load_manifest(channel)
        key = self._channel_key(manifest, passphrase)
        path = self._chan_dir(channel) / ("msg_%s.json" % msg_id)
        if not path.exists():
            raise EphemeraError("unknown message: %s" % msg_id)
        record = json.loads(path.read_text(encoding=ENC))
        body = open_seal(key, bytes.fromhex(record["blob_hex"])).decode(ENC)
        self._log_access(channel, msg_id, reader)
        return {
            "id": msg_id,
            "author": record["author"],
            "created_at": record["created_at"],
            "expires_at": record["expires_at"],
            "forwarding_discouraged": record.get("forwarding_discouraged", False),
            "body": body,
        }

    def _log_access(self, channel: str, msg_id: str, reader: str) -> None:
        d = self._chan_dir(channel)
        line = json.dumps(
            {
                "ts": _now(),
                "msg_id": msg_id,
                "reader": reader,
                "note": (
                    "forwarding_discouraged was displayed"
                    if self._fwd_flag(d, msg_id)
                    else "read"
                ),
            }
        )
        with (d / "access.jsonl").open("a", encoding=ENC) as fh:
            fh.write(line + "\n")

    def _fwd_flag(self, d: Path, msg_id: str) -> bool:
        p = d / ("msg_%s.json" % msg_id)
        if not p.exists():
            return False
        return bool(json.loads(p.read_text(encoding=ENC)).get("forwarding_discouraged"))

    def access_log(self, channel: str) -> List[Dict[str, Any]]:
        self._load_manifest(channel)
        p = self._chan_dir(channel) / "access.jsonl"
        if not p.exists():
            return []
        return [
            json.loads(line)
            for line in p.read_text(encoding=ENC).splitlines()
            if line.strip()
        ]

    # -- expiry / true delete -----------------------------------------------
    def _secure_overwrite(self, path: Path) -> None:
        size = path.stat().st_size
        with path.open("r+b") as fh:
            for _ in range(_OVERWRITE_PASSES):
                fh.seek(0)
                fh.write(os.urandom(size))
                fh.flush()
            fh.seek(0)
            fh.write(b"\x00" * size)
            fh.flush()

    def _last_receipt_hash(self, channel: str) -> bytes:
        p = self._chan_dir(channel) / "receipts.jsonl"
        prev = GENESIS
        if p.exists():
            for line in p.read_text(encoding=ENC).splitlines():
                if line.strip():
                    prev = bytes.fromhex(json.loads(line)["hash"])
        return prev

    def _append_receipt(
        self, channel: str, event: str, msg_id: str, detail: str
    ) -> Dict[str, Any]:
        prev = self._last_receipt_hash(channel)
        payload = json.dumps(
            {
                "ts": _now(),
                "channel": channel,
                "event": event,
                "msg_id": msg_id,
                "detail": detail,
                "prev": prev.hex(),
            },
            sort_keys=True,
        ).encode(ENC)
        h = chain_hash(prev, payload).hex()
        receipt = {"hash": h, "payload": json.loads(payload.decode(ENC))}
        with (self._chan_dir(channel) / "receipts.jsonl").open("a", encoding=ENC) as fh:
            fh.write(json.dumps(receipt) + "\n")
        return receipt

    def sweep(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """Delete expired messages (secure overwrite) + hash-chained receipts."""
        channels = [channel] if channel else self.list_channels()
        deleted: List[Dict[str, Any]] = []
        now = _now()
        for ch in channels:
            for path, record in list(self._iter_records(ch)):
                if record["expires_at"] <= now:
                    self._secure_overwrite(path)
                    path.unlink()
                    receipt = self._append_receipt(
                        ch,
                        "deleted",
                        record["id"],
                        "expired at %.0f; %d overwrite passes"
                        % (record["expires_at"], _OVERWRITE_PASSES),
                    )
                    deleted.append(
                        {
                            "channel": ch,
                            "id": record["id"],
                            "receipt": receipt["hash"][:16],
                        }
                    )
        return deleted

    def verify_receipts(self, channel: str) -> Dict[str, Any]:
        """Verify the hash chain of deletion receipts. Returns count/ok."""
        self._load_manifest(channel)
        p = self._chan_dir(channel) / "receipts.jsonl"
        prev = GENESIS
        count = 0
        if p.exists():
            for line in p.read_text(encoding=ENC).splitlines():
                if not line.strip():
                    continue
                receipt = json.loads(line)
                payload = json.dumps(receipt["payload"], sort_keys=True).encode(ENC)
                expect = chain_hash(prev, payload).hex()
                if (
                    receipt["hash"] != expect
                    or receipt["payload"]["prev"] != prev.hex()
                ):
                    return {
                        "ok": False,
                        "count": count,
                        "channel": channel,
                        "error": "chain broken at receipt %d" % count,
                    }
                prev = bytes.fromhex(receipt["hash"])
                count += 1
        return {"ok": True, "count": count, "channel": channel}
