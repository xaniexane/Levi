"""Tamper-evident audit trail for LEVI Oath.

Append-only JSONL at ``<oath home>/audit.jsonl``.  Each entry::

    {"seq": 7, "ts": "2026-09-15T23:00:00Z", "prev_hash": "abc…",
     "payload": {...}, "sha256": "def…"}

where ``sha256 = SHA256(canonical_json({seq, ts, prev_hash, payload}))``
and ``prev_hash`` is the previous entry's ``sha256`` (``"GENESIS"`` for
the first entry).  Any modification of a payload breaks the chain.

Checkpoints: the owner (or daemon) periodically writes a GPG-clearsigned
checkpoint to ``<oath home>/checkpoints/checkpoint-<seq>.asc`` binding
``seq`` to the chain hash.  ``verify()`` replays the whole chain and
checks every checkpoint signature against the owner's fingerprint.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

from levi.oath import AUDIT_FILE, CHECKPOINTS_DIR

__all__ = [
    "AuditLog",
    "AuditError",
    "canonical_entry_bytes",
    "entry_hash",
]

_GENESIS = "GENESIS"
_CHECKPOINT_RE = re.compile(r"^checkpoint-(\d+)\.asc$")


class AuditError(Exception):
    """Raised when the audit chain fails verification."""


def canonical_entry_bytes(entry: dict[str, Any]) -> bytes:
    """Canonical bytes hashed for an entry (excludes the ``sha256`` field)."""
    core = {k: entry[k] for k in ("seq", "ts", "prev_hash", "payload")}
    return (json.dumps(core, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def entry_hash(entry: dict[str, Any]) -> str:
    """Compute the chain hash for an entry dict."""
    return hashlib.sha256(canonical_entry_bytes(entry)).hexdigest()


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class AuditLog:
    """Append-only audit log with hash chaining."""

    path: Optional[Path] = None

    def __post_init__(self) -> None:
        self.path = self.path or AUDIT_FILE()

    # -- reading ---------------------------------------------------------
    def entries(self) -> Iterator[dict[str, Any]]:
        """Yield entries in file order; skips blank lines."""
        assert self.path is not None
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def last(self) -> Optional[dict[str, Any]]:
        prev: Optional[dict[str, Any]] = None
        for entry in self.entries():
            prev = entry
        return prev

    # -- writing ----------------------------------------------------------
    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Append ``payload`` as a new chained entry.  Returns the entry."""
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        last = self.last()
        entry = {
            "seq": 0 if last is None else int(last["seq"]) + 1,
            "ts": _utcnow(),
            "prev_hash": _GENESIS if last is None else str(last["sha256"]),
            "payload": payload,
        }
        entry["sha256"] = entry_hash(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return entry

    # -- verification ------------------------------------------------------
    def verify(self) -> dict[str, Any]:
        """Replay the chain.  Returns ``{"ok": True, "entries": n, ...}``.

        Raises :class:`AuditError` on the first broken link, naming the
        offending ``seq``.
        """
        count = 0
        prev_hash = _GENESIS
        expected_seq = 0
        for entry in self.entries():
            seq = entry.get("seq")
            if seq != expected_seq:
                raise AuditError(
                    f"seq break at file position {count}: got {seq}, want {expected_seq}"
                )
            if entry.get("prev_hash") != prev_hash:
                raise AuditError(f"entry {seq}: prev_hash mismatch — chain tampered")
            if entry.get("sha256") != entry_hash(entry):
                raise AuditError(f"entry {seq}: payload hash mismatch — entry tampered")
            prev_hash = str(entry["sha256"])
            expected_seq += 1
            count += 1
        return {"ok": True, "entries": count, "head": prev_hash}

    # -- checkpoints ---------------------------------------------------------
    def checkpoint(self, *, signer: Optional[str] = None) -> Path:
        """Write a GPG-clearsigned checkpoint binding ``seq`` to the head hash.

        ``signer`` is a ``--local-user`` selector; when omitted gpg uses its
        default key.  Returns the checkpoint path.
        """
        from levi.oath.keys import (
            gpg_sign_args,
            run_gpg,
        )  # local import: keys is optional at runtime

        assert self.path is not None
        head = self.last()
        if head is None:
            raise AuditError("cannot checkpoint an empty audit log")
        CHECKPOINTS_DIR().mkdir(parents=True, exist_ok=True)
        body = {
            "oath_checkpoint": 1,
            "seq": head["seq"],
            "head": head["sha256"],
            "ts": _utcnow(),
        }
        raw = (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")
        target = CHECKPOINTS_DIR() / f"checkpoint-{head['seq']}.asc"
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(raw)
        cmd = gpg_sign_args() + ["--armor", "--clearsign", "--output", str(target)]
        if signer:
            cmd += ["--local-user", signer]
        cmd.append(str(tmp))
        try:
            run_gpg(*cmd)
        finally:
            tmp.unlink(missing_ok=True)
        return target

    def verify_checkpoints(
        self, owner_fingerprint: Optional[str] = None
    ) -> dict[str, Any]:
        """Verify every checkpoint: signature valid, seq/hash match the chain.

        Rebuilds the head hash per seq from the log, then checks each
        checkpoint's clearsigned body against it.  The chain is replayed
        first — checkpoints are only meaningful on a valid chain.  Returns
        a summary dict; raises :class:`AuditError` on failure.
        """
        from levi.oath.trust import verify_clearsigned  # local import

        self.verify()  # replay the chain; stored hashes untrusted until this passes

        # Head hash per seq, recomputed from the (now validated) chain.
        heads: dict[int, str] = {}
        for entry in self.entries():
            heads[int(entry["seq"])] = str(entry["sha256"])

        checked = 0
        cdir = CHECKPOINTS_DIR()
        if cdir.is_dir():
            for path in sorted(cdir.glob("checkpoint-*.asc")):
                match = _CHECKPOINT_RE.match(path.name)
                if not match:
                    continue
                blob = path.read_bytes()
                valid, fpr, _uid, detail = verify_clearsigned(blob)
                if not valid:
                    raise AuditError(
                        f"{path.name}: bad checkpoint signature ({detail})"
                    )
                if owner_fingerprint and (fpr or "").upper().replace(
                    " ", ""
                ) != owner_fingerprint.upper().replace(" ", ""):
                    raise AuditError(f"{path.name}: not signed by the owner")
                # Extract the JSON body from the clearsigned message.
                body_text = _clearsign_body(blob)
                try:
                    body = json.loads(body_text)
                except json.JSONDecodeError as exc:
                    raise AuditError(
                        f"{path.name}: checkpoint body not JSON: {exc}"
                    ) from exc
                seq = int(body.get("seq", -1))
                want = heads.get(seq)
                if want is None:
                    raise AuditError(f"{path.name}: seq {seq} not in audit log")
                if body.get("head") != want:
                    raise AuditError(
                        f"{path.name}: head hash mismatch — log tampered after checkpoint"
                    )
                checked += 1
        return {"ok": True, "checkpoints": checked}


def _clearsign_body(blob: bytes) -> str:
    """Extract the cleartext body from a clearsigned message."""
    text = blob.decode("utf-8", "replace")
    lines = text.splitlines()
    body: list[str] = []
    in_headers = True
    past_blank = False
    for ln in lines:
        if ln.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
            in_headers = True
            continue
        if in_headers:
            if ln.strip() == "" and not past_blank:
                past_blank = True
                in_headers = False
            continue
        if ln.startswith("-----BEGIN PGP SIGNATURE-----"):
            break
        # Dash-unescaping per RFC 4880 §7.1.
        body.append(ln[2:] if ln.startswith("- ") else ln)
    return "\n".join(body) + "\n"
