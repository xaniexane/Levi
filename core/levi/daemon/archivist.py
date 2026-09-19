"""Archivist — periodic state snapshots with a hash-chained receipt log.

When something goes wrong, the first question is "what did the state look
like before?" The archivist answers it: on every tick it takes a snapshot
(manifest of file paths + sizes + sha256 digests under configured roots)
and appends a receipt to a hash-chained JSONL log. Each receipt embeds
the previous receipt's hash, so a tampered or truncated log is
detectable — ``verify_chain()`` revalidates the whole chain.

Snapshots are manifests, not copies: cheap, deterministic, and honest
about what they cover. The archivist never snapshots its own snapshot
directory (self-reference would churn every tick).

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.archivist`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_STATE_DIR = Path.home() / ".levi" / "archivist"

#: Subtrees the archivist never walks into.
EXCLUDE_PARTS = ("archivist", "__pycache__", ".git", "node_modules")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class Snapshot:
    """One state manifest."""

    at: str = ""
    roots: List[str] = field(default_factory=list)
    files: List[Dict[str, Any]] = field(default_factory=list)
    manifest_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChainReceipt:
    seq: int
    at: str
    snapshot: str
    manifest_hash: str
    prev_hash: str
    hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchivistReport:
    """Outcome of one archivist tick."""

    at: str = ""
    snapshot: str = ""
    files: int = 0
    chain_ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Archivist:
    """Snapshot manifests + hash-chained receipts for auditability."""

    def __init__(
        self,
        home: Optional[Path] = None,
        roots: Optional[List[Path]] = None,
    ) -> None:
        self.home = Path(home) if home is not None else Path.home()
        self.state_dir = self.home / ".levi" / "archivist"
        self.snapshots_dir = self.state_dir / "snapshots"
        self.receipts_path = self.state_dir / "receipts.jsonl"
        if roots is not None:
            self.roots = [Path(r) for r in roots]
        else:
            self.roots = [self.home / ".levi"]

    # -- snapshots ---------------------------------------------------------

    def _excluded(self, path: Path) -> bool:
        return any(part in EXCLUDE_PARTS for part in path.parts)

    def take_snapshot(self) -> Snapshot:
        """Walk the roots and manifest every regular file."""
        snap = Snapshot(at=_utcnow_iso(), roots=[str(r) for r in self.roots])
        entries: List[Dict[str, Any]] = []
        for root in self.roots:
            if not root.is_dir() or self._excluded(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                d = Path(dirpath)
                dirnames[:] = [x for x in dirnames if not self._excluded(d / x)]
                for name in filenames:
                    p = d / name
                    if self._excluded(p):
                        continue
                    try:
                        if not p.is_file() or p.is_symlink():
                            continue
                        size = p.stat().st_size
                    except OSError:
                        continue
                    digest = _sha256_file(p)
                    if digest is None:
                        continue
                    entries.append(
                        {
                            "path": str(p.relative_to(root)),
                            "root": str(root),
                            "size": size,
                            "sha256": digest,
                        }
                    )
        entries.sort(key=lambda e: (e["root"], e["path"]))
        snap.files = entries
        snap.manifest_hash = hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return snap

    def _save_snapshot(self, snap: Snapshot) -> str:
        name = snap.at.replace(":", "").replace("+", "p") + ".json"
        path = self.snapshots_dir / name
        _atomic_write(path, json.dumps(snap.to_dict(), indent=2))
        return name

    # -- hash chain ---------------------------------------------------------

    def _last_receipt(self) -> Optional[Dict[str, Any]]:
        try:
            lines = self.receipts_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return None
        except OSError:
            return None
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and "seq" in rec and "hash" in rec:
                return rec
        return None

    @staticmethod
    def _chain_hash(seq: int, manifest_hash: str, prev_hash: str) -> str:
        return hashlib.sha256(
            f"{seq}:{manifest_hash}:{prev_hash}".encode("utf-8")
        ).hexdigest()

    def _append_receipt(self, snapshot_name: str, snap: Snapshot) -> ChainReceipt:
        last = self._last_receipt()
        seq = int(last["seq"]) + 1 if last else 0
        prev_hash = str(last["hash"]) if last else "GENESIS"
        receipt = ChainReceipt(
            seq=seq,
            at=snap.at,
            snapshot=snapshot_name,
            manifest_hash=snap.manifest_hash,
            prev_hash=prev_hash,
            hash=self._chain_hash(seq, snap.manifest_hash, prev_hash),
        )
        self.receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.receipts_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict(), separators=(",", ":")) + "\n")
        try:
            os.chmod(self.receipts_path, 0o600)
        except OSError:
            pass
        return receipt

    def verify_chain(self) -> Tuple[bool, str]:
        """Revalidate every receipt link. Returns (ok, detail)."""
        try:
            lines = self.receipts_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return True, "no receipts yet — chain empty, not broken"
        except OSError as exc:
            return False, f"cannot read receipts: {exc}"
        prev_hash = "GENESIS"
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                return False, f"corrupt receipt line at position {count}"
            try:
                seq = int(rec["seq"])
                expected = self._chain_hash(
                    seq, str(rec["manifest_hash"]), str(rec["prev_hash"])
                )
            except (KeyError, TypeError, ValueError):
                return False, f"malformed receipt at position {count}"
            if rec["prev_hash"] != prev_hash or rec["hash"] != expected:
                return False, f"chain broken at seq {seq}"
            prev_hash = rec["hash"]
            count += 1
        return True, f"chain valid: {count} receipt(s)"

    # -- tick ---------------------------------------------------------------

    def tick(self) -> ArchivistReport:
        """Take a snapshot and chain its receipt. Never raises."""
        report = ArchivistReport(at=_utcnow_iso())
        try:
            snap = self.take_snapshot()
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"snapshot failed: {exc}")
            report.chain_ok = False
            return report
        try:
            name = self._save_snapshot(snap)
            self._append_receipt(name, snap)
            report.snapshot = name
            report.files = len(snap.files)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"persist failed: {exc}")
            report.chain_ok = False
            return report
        ok, _ = self.verify_chain()
        report.chain_ok = ok
        return report

    def check(self) -> tuple:
        """Lightweight coherence check for the supervisor (never raises)."""
        try:
            ok, detail = self.verify_chain()
            snaps = (
                len(list(self.snapshots_dir.glob("*.json")))
                if self.snapshots_dir.is_dir()
                else 0
            )
            if not ok:
                return False, f"archivist receipt chain BROKEN: {detail}"
            return True, f"{snaps} snapshot(s); {detail}"
        except Exception as exc:  # noqa: BLE001
            return False, f"archivist check failed: {exc}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.archivist")
    ap.parse_args(argv)
    report = Archivist().tick()
    print(
        "archivist tick: snapshot=%s files=%d chain_ok=%s"
        % (report.snapshot or "none", report.files, report.chain_ok)
    )
    for err in report.errors:
        print(f"  error: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
