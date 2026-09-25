"""Cybrus BACK backup-integrity — hash-chained manifests for the encrypted archives.

The encrypted backup archives (``~/.levi/cybrus/backups/*.7z``) are the
organism's memory at rest. This module makes tampering DETECTABLE: every
archive is recorded in an append-only, hash-chained manifest — each entry
commits to its predecessor's hash — and :meth:`ManifestEngine.verify`
recomputes the whole chain and re-hashes the archives on disk.

LAWS (binding — what must always hold):
  BM1 Every manifest entry is hash-chained to its predecessor
      (``entry_hash = sha256(prev_hash || canonical(entry))``); the
      genesis entry chains to the literal ``"GENESIS"``. No entry stands
      alone.
  BM2 Verification recomputes the FULL chain — every link, not just the
      tip. The first broken link fails the whole verification, closed:
      ``ok=False`` with the exact failing sequence number.
  BM3 Re-hashing the archives on disk is part of verification: a modified
      archive fails even when the manifest chain is intact. Tampering is
      detectable, not preventable — the manifest says WHAT changed.
  BM4 The manifest is append-only. This module exposes no edit, no
      delete, no rewrite. A corrupt manifest is quarantined for
      forensics and the engine starts a fresh chain rather than
      inventing continuity.

Proof: tests/test_cybrus_backup_manifest.py — invariant tests, honestly
named (machine-checked, not formally proven).

Stdlib-only, no network. Manifest: ``~/.levi/cybrus/backup-manifest.jsonl``
(``LEVI_HOME`` override honored). Every record and every verification
is audit-logged (metadata only: names, digests, sizes — never archive
contents).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Chain anchor for the first entry (BM1).
GENESIS = "GENESIS"

#: The declared laws, machine-readable (same pattern as enforce.LAWS).
LAWS = (
    ("BM1", "Every manifest entry is hash-chained to its predecessor; genesis chains to 'GENESIS'."),
    ("BM2", "Verification recomputes the full chain; the first broken link fails closed with its sequence number."),
    ("BM3", "Verification re-hashes archives on disk; a modified archive fails even with an intact chain."),
    ("BM4", "The manifest is append-only: no edit, no delete, no rewrite API; corrupt manifests are quarantined."),
)

_MANIFEST_NAME = "backup-manifest.jsonl"
_CHUNK = 1024 * 1024  # 1 MiB — archives are GB-scale; never read whole


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ManifestError(Exception):
    """The backup manifest refused an operation (fail closed)."""


def _paths():  # noqa: D103 - private helper, same rationale as enforce.py
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, str(actor), dict(details or {}))


def _canonical(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _entry_hash(prev_hash: str, entry: Dict[str, Any]) -> str:
    """BM1: each entry commits to its predecessor's hash."""
    body = entry.copy()
    body.pop("entry_hash", None)
    return hashlib.sha256(
        (prev_hash + "\n" + _canonical(body)).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class ManifestEngine:
    """Hash-chained integrity manifest for the encrypted backup archives."""

    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        manifest_path: Optional[Path] = None,
    ) -> None:
        p = _paths()
        self.backup_dir = (
            Path(backup_dir) if backup_dir else p.cybrus_dir() / "backups"
        )
        self.manifest_path = (
            Path(manifest_path) if manifest_path else p.cybrus_dir() / _MANIFEST_NAME
        )

    # -- manifest I/O ------------------------------------------------------

    def _read_entries(self) -> List[Dict[str, Any]]:
        """Read all entries. A corrupt manifest is quarantined (BM4) and a
        fresh chain started — continuity is never invented."""
        if not self.manifest_path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            for lineno, line in enumerate(
                self.manifest_path.read_text(encoding="utf-8").splitlines()
            ):
                if not line.strip():
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    raise ValueError(f"line {lineno}: not an object")
                entries.append(entry)
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
            from levi.cybrus._paths import CorruptStoreError

            bad = self.manifest_path.with_name(
                f"{self.manifest_path.stem}.corrupt-{int(time.time())}.jsonl"
            )
            self.manifest_path.replace(bad)
            raise CorruptStoreError(
                f"backup manifest corrupt ({exc}); quarantined to {bad.name} — "
                "a fresh chain starts on next record"
            ) from exc
        return entries

    def _append_entry(self, entry: Dict[str, Any]) -> None:
        """Append one JSONL line. Caller must hold the manifest lock (seq is
        assigned under it so concurrent recorders cannot fork the chain)."""
        line = _canonical(entry) + "\n"
        fd = os.open(self.manifest_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    # -- recording ---------------------------------------------------------

    def record(self, archive: Path | str, recorded_by: str) -> Dict[str, Any]:
        """Record one archive in the chain. Returns the entry.

        The archive must live inside ``backup_dir`` (path traversal is
        refused) and must be a regular file. The entry records name,
        size, and sha256 — metadata only, never contents.
        """
        recorded_by = str(recorded_by or "").strip()
        if not recorded_by:
            raise ManifestError("recorded_by is required")
        target = Path(archive)
        try:
            resolved = target.resolve()
            base = self.backup_dir.resolve()
            resolved.relative_to(base)
        except (ValueError, OSError) as exc:
            raise ManifestError(
                f"archive {target} is outside the backup directory; refusing"
            ) from exc
        if not resolved.is_file():
            raise ManifestError(f"archive {target} is not a regular file")
        digest = _sha256_file(resolved)
        size = resolved.stat().st_size
        name = resolved.name

        p = _paths()
        with p.store_lock(self.manifest_path):
            entries = self._read_entries()
            prev_hash = entries[-1]["entry_hash"] if entries else GENESIS
            entry = {
                "seq": len(entries),
                "name": name,
                "size_bytes": size,
                "sha256": digest,
                "prev_hash": prev_hash,
                "recorded_at": _utcnow_iso(),
                "recorded_by": recorded_by,
            }
            entry["entry_hash"] = _entry_hash(prev_hash, entry)
            self._append_entry(entry)

        _audit(
            "backup.manifest.recorded",
            f"manifest:{recorded_by}",
            {
                "seq": entry["seq"],
                "name": name,
                "size_bytes": size,
                "sha256": digest[:16],
                "entry_hash": entry["entry_hash"][:16],
            },
        )
        return dict(entry)

    def snapshot(self, recorded_by: str) -> Dict[str, Any]:
        """Record every archive in the backup dir not already recorded.

        Idempotent: an (name, sha256) pair already in the manifest is
        skipped, never re-chained. Returns counts.
        """
        if not self.backup_dir.is_dir():
            raise ManifestError(f"backup dir {self.backup_dir} does not exist")
        with _paths().store_lock(self.manifest_path):
            known = {(e.get("name"), e.get("sha256")) for e in self._read_entries()}
        recorded, skipped = [], []
        for child in sorted(self.backup_dir.iterdir()):
            if not child.is_file():
                continue
            digest = _sha256_file(child)
            if (child.name, digest) in known:
                skipped.append(child.name)
                continue
            recorded.append(self.record(child, recorded_by)["name"])
        _audit(
            "backup.manifest.snapshot",
            f"manifest:{recorded_by}",
            {"recorded": len(recorded), "skipped": len(skipped)},
        )
        return {"recorded": recorded, "skipped": skipped}

    # -- verification (BM2/BM3) --------------------------------------------

    def verify(self, *, rehash_archives: bool = True) -> Dict[str, Any]:
        """Verify the manifest: full chain recompute (BM2) + archive
        re-hash (BM3). Fails closed: ``ok=False`` with the exact failing
        sequence numbers and reasons."""
        entries = self._read_entries()
        failures: List[Dict[str, Any]] = []
        for i, entry in enumerate(entries):
            expected_prev = entries[i - 1]["entry_hash"] if i > 0 else GENESIS
            if entry.get("prev_hash") != expected_prev:
                failures.append(
                    {
                        "seq": entry.get("seq", i),
                        "reason": "chain_break",
                        "detail": "prev_hash does not match the previous entry_hash",
                    }
                )
            if entry.get("entry_hash") != _entry_hash(
                entry.get("prev_hash", ""), entry
            ):
                failures.append(
                    {
                        "seq": entry.get("seq", i),
                        "reason": "entry_hash_mismatch",
                        "detail": "recomputed entry_hash differs — entry was modified",
                    }
                )
            if rehash_archives:
                name = entry.get("name")
                target = self.backup_dir / name if isinstance(name, str) else None
                if target is None or not target.is_file():
                    failures.append(
                        {"seq": entry.get("seq", i), "reason": "archive_missing",
                         "detail": f"archive {name!r} not on disk"}
                    )
                elif _sha256_file(target) != entry.get("sha256"):
                    failures.append(
                        {"seq": entry.get("seq", i), "reason": "archive_tampered",
                         "detail": f"archive {name!r} hash differs from manifest"}
                    )
        ok = not failures
        _audit(
            "backup.manifest.verified",
            "manifest:verifier",
            {
                "ok": ok,
                "checked": len(entries),
                "failures": len(failures),
                "first_failure_seq": failures[0]["seq"] if failures else None,
            },
        )
        return {
            "ok": ok,
            "checked": len(entries),
            "failures": failures,
            "tip": entries[-1]["entry_hash"] if entries else None,
        }

    def status(self) -> Dict[str, Any]:
        """Lightweight status: entry count, tip hash, backup dir listing."""
        entries = self._read_entries()
        archives = (
            sorted(
                (c.name, c.stat().st_size)
                for c in self.backup_dir.iterdir()
                if c.is_file()
            )
            if self.backup_dir.is_dir()
            else []
        )
        recorded_names = {e.get("name") for e in entries}
        return {
            "manifest_entries": len(entries),
            "tip": entries[-1]["entry_hash"][:16] if entries else None,
            "archives_on_disk": len(archives),
            "unrecorded_archives": [
                n for n, _ in archives if n not in recorded_names
            ],
        }

    def describe_posture(self) -> Dict[str, Any]:
        """Honest posture of the backup-integrity machinery."""
        return {
            "organism": "levi",
            "organ": "levi.cybrus.backup_manifest",
            "role": "tamper-DETECTION for encrypted backup archives: hash-chained manifest + verify tooling",
            "prevents_tampering": False,  # honest: detection, not prevention
            "detects_tampering": True,
            "append_only": True,  # BM4: no edit/delete/rewrite API
            "network": "none — stdlib only",
            "backup_dir": str(self.backup_dir),
            "manifest": str(self.manifest_path),
            "laws": [lid for lid, _ in LAWS],
        }
