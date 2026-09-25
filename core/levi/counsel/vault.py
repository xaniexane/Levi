"""Local counsel vault: 0600 storage, never synced anywhere.

Layout under the vault root (default ``~/.levi/counsel/vault``):

* ``docs/<doc_id>.orig``    — the original bytes, 0600
* ``docs/<doc_id>.txt``     — the extracted text, 0600 (accepted docs only)
* ``quarantine/<doc_id>.orig`` — quarantined originals, 0600, not indexed
* ``manifest.jsonl``        — append-only record of every intake decision, 0600

Directories are created 0700. Every write goes through ``_locked_open``,
which sets umask 0o077 for the duration so nothing lands world-readable
even for a instant. Permissions are re-asserted (chmod) on every store so
a stray umask elsewhere in the process cannot loosen them.

This vault is the unreplicable physics: the privileged document never
leaves the machine. There is no server to subpoena, no sync to leak.
"""

from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from levi.counsel.gates import (
    VERDICT_ACCEPT,
    VERDICT_QUARANTINE,
    VERDICT_REJECT,
)
from levi.counsel.intake import IntakeProposal
from levi.counsel.verify import Verification

FILE_MODE = 0o600
DIR_MODE = 0o700

DEFAULT_ROOT = Path.home() / ".levi" / "counsel" / "vault"


@contextmanager
def _locked_open() -> Iterator[None]:
    """Run a block with umask 0o077 so created files are owner-only."""
    old = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old)


@dataclass
class StoredDoc:
    doc_id: str
    source_name: str
    verdict: str
    quality: str
    size_bytes: int
    stored_at: str
    reason: str
    warnings: List[str] = field(default_factory=list)
    quarantine_causes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CounselVault:
    """Owner-local document vault. Opt-in by construction: a vault only
    exists because the owner created it and put documents in it."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        with _locked_open():
            self.root.mkdir(parents=True, exist_ok=True)
            os.chmod(self.root, DIR_MODE)
            for sub in ("docs", "quarantine"):
                d = self.root / sub
                d.mkdir(exist_ok=True)
                os.chmod(d, DIR_MODE)
        manifest = self.root / "manifest.jsonl"
        if not manifest.exists():
            with _locked_open():
                manifest.touch()
                os.chmod(manifest, FILE_MODE)
        else:
            os.chmod(manifest, FILE_MODE)
        self._manifest_cache: Optional[List[StoredDoc]] = None

    # -- storage -----------------------------------------------------

    def store(self, proposal: IntakeProposal, verification: Verification) -> StoredDoc:
        """Store a verified proposal. ACCEPT writes original + extracted
        text under docs/; QUARANTINE writes the original under quarantine/
        only; REJECT writes nothing. Every decision is appended to the
        manifest, including rejections."""
        verdict = verification.verdict
        if verdict not in (VERDICT_ACCEPT, VERDICT_QUARANTINE, VERDICT_REJECT):
            raise ValueError(f"unknown verdict: {verdict!r}")

        source = Path(proposal.source_path)
        stored_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        doc = StoredDoc(
            doc_id=proposal.doc_id,
            source_name=source.name,
            verdict=verdict,
            quality=proposal.extraction.quality,
            size_bytes=proposal.extraction.size_bytes,
            stored_at=stored_at,
            reason=verification.reason,
            warnings=list(proposal.extraction.warnings),
            quarantine_causes=list(verification.quarantine_causes),
        )

        if verdict != VERDICT_REJECT:
            target_dir = self.root / (
                "docs" if verdict == VERDICT_ACCEPT else "quarantine"
            )
            with _locked_open():
                raw = source.read_bytes()
                orig = target_dir / f"{doc.doc_id}.orig"
                orig.write_bytes(raw)
                os.chmod(orig, FILE_MODE)
                if verdict == VERDICT_ACCEPT:
                    txt = self.root / "docs" / f"{doc.doc_id}.txt"
                    txt.write_text(proposal.extraction.text, encoding="utf-8")
                    os.chmod(txt, FILE_MODE)

        with _locked_open():
            with open(self.root / "manifest.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(doc.to_dict()) + "\n")
            os.chmod(self.root / "manifest.jsonl", FILE_MODE)
        self._manifest_cache = None
        return doc

    def has(self, doc_id: str) -> bool:
        """True when the doc's bytes are on disk (accepted or quarantined)."""
        return (self.root / "docs" / f"{doc_id}.orig").exists() or (
            self.root / "quarantine" / f"{doc_id}.orig"
        ).exists()

    def stored_text(self, doc_id: str) -> Optional[str]:
        """Extracted text for an ACCEPTED doc; None for quarantined docs —
        quarantine means not indexed and not retrievable as text."""
        p = self.root / "docs" / f"{doc_id}.txt"
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")

    # -- manifest ----------------------------------------------------

    def manifest(self) -> List[StoredDoc]:
        if self._manifest_cache is None:
            docs: List[StoredDoc] = []
            with open(self.root / "manifest.jsonl", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        docs.append(StoredDoc(**json.loads(line)))
            self._manifest_cache = docs
        return list(self._manifest_cache)

    def assert_permissions(self) -> List[str]:
        """Walk the vault and report any file/dir not at 0600/0700.
        Returns the list of offending paths (empty = clean)."""
        bad: List[str] = []
        for path in [self.root, self.root / "docs", self.root / "quarantine"]:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode != DIR_MODE:
                bad.append(f"{path} mode {oct(mode)}")
        for path in self.root.rglob("*"):
            if path.is_file():
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode != FILE_MODE:
                    bad.append(f"{path} mode {oct(mode)}")
        return bad
