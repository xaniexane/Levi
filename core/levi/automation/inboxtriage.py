"""Inbox triage automation — the dropbox that files itself.

LAWS (law-guard-prove):
1. NOTHING IS EVER DELETED. Files move into category drawers inside the
   inbox root; a file is never unlinked, overwritten, or merged. Provenance
   survives every move in an append-only JSONL ledger.
2. DETERMINISTIC. The same set of files scanned in the same order always
   yields the same destination names (collision suffixes count up
   deterministically), so a run is reproducible and re-runnable.
3. BOUNDED. Every move lands inside the inbox root. A path that escapes
   the root (symlink games included) is refused, never followed.

Stdlib only. Local-first: scans a directory, moves files, writes a
ledger — no network, no credentials, no confirmation surface.

Conventions mirror levi.automation.watchers (poll-style scan, UTC ledger).
"""

from __future__ import annotations

import csv as _csv  # noqa: F401 (re-exported for callers that read the ledger)
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

LEDGER_DIR = ".inboxtriage"
LEDGER_FILE = "ledger.jsonl"

# Extension -> category drawer. First match wins on the lowercase suffix.
_CATEGORY_MAP: List[Tuple[str, str]] = [
    (".png,.jpg,.jpeg,.gif,.webp,.bmp,.svg,.tif,.tiff,.heic", "images"),
    (".mp3,.wav,.flac,.ogg,.m4a,.aac,.opus", "audio"),
    (".mp4,.mov,.mkv,.webm,.avi,.m4v", "video"),
    (
        ".pdf,.doc,.docx,.odt,.rtf,.txt,.md,.epub,.ppt,.pptx,.xls,.xlsx,.csv",
        "documents",
    ),
    (".zip,.tar,.gz,.tgz,.bz2,.xz,.7z,.rar", "archives"),
    (
        ".py,.js,.ts,.tsx,.jsx,.java,.kt,.go,.rs,.c,.h,.cpp,.sh,.html,.css,.json,.yaml,.yml,.toml",
        "code",
    ),
    (".db,.sqlite,.sqlite3,.parquet", "data"),
]

# Magic bytes -> category (checked before the extension map, so a renamed
# file still lands in the right drawer).
_MAGIC_MAP: List[Tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "images"),
    (b"\xff\xd8\xff", "images"),
    (b"GIF87a", "images"),
    (b"GIF89a", "images"),
    (b"RIFF", "audio"),  # WAV/AVI — extension map refines when known
    (b"ID3", "audio"),
    (b"%PDF", "documents"),
    (b"PK\x03\x04", "archives"),
    (b"\x1f\x8b\x08", "archives"),  # gzip
]


def classify(path: Path) -> str:
    """Return the category drawer for a file (magic first, then extension)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        head = b""
    for magic, category in _MAGIC_MAP:
        if head.startswith(magic):
            return category
    suffix = path.suffix.lower()
    for exts, category in _CATEGORY_MAP:
        if suffix and suffix in exts.split(","):
            return category
    return "misc"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class TriageMove:
    source: str  # path relative to inbox root, before the move
    destination: str  # path relative to inbox root, after the move
    category: str
    size_bytes: int
    sha256: str


@dataclass
class TriageReport:
    inbox: str
    moved: List[TriageMove] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # relative paths
    refused: List[str] = field(default_factory=list)  # escaped root / not files

    @property
    def moved_count(self) -> int:
        return len(self.moved)


def _safe_destination(root: Path, category: str, name: str) -> Path:
    """Resolve a drawer destination that is guaranteed inside root.

    Collision-safe: ``name``, ``name-2``, ``name-3``, ... — deterministic.
    Raises RefusedPath when the candidate escapes the root.
    """
    drawer = root / category
    drawer.mkdir(parents=True, exist_ok=True)
    candidate = drawer / name
    stem, suffix = os.path.splitext(name)
    n = 1
    while candidate.exists():
        n += 1
        candidate = drawer / f"{stem}-{n}{suffix}"
    resolved = candidate.resolve()
    if resolved != candidate and not str(resolved).startswith(
        str(root.resolve()) + os.sep
    ):
        raise RefusedPath(name)
    return candidate


class RefusedPath(Exception):
    """A path escaped the inbox root (symlink games) — refused, never followed."""


def _ledger_append(root: Path, move: TriageMove) -> None:
    ledger_dir = root / LEDGER_DIR
    ledger_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "at": _utcnow(),
        "source": move.source,
        "destination": move.destination,
        "category": move.category,
        "size_bytes": move.size_bytes,
        "sha256": move.sha256,
    }
    with open(ledger_dir / LEDGER_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def triage(inbox: str | Path, *, dry_run: bool = False) -> TriageReport:
    """File every loose file in *inbox* into its category drawer.

    Law 1: nothing is deleted — files move and every move is ledgered.
    Law 2: deterministic — candidates are scanned in sorted order, suffix
    numbering counts up from 2.
    Law 3: bounded — destinations are confined to the inbox root.
    """
    root = Path(inbox).resolve()
    report = TriageReport(inbox=str(root))
    if not root.is_dir():
        report.refused.append(str(inbox))
        return report

    root_real = root.resolve()
    entries = sorted(
        (p for p in root.iterdir() if p.name != LEDGER_DIR),
        key=lambda p: p.name,
    )
    for entry in entries:
        rel = entry.name
        try:
            real = entry.resolve()
        except OSError:
            report.refused.append(rel)
            continue
        if not real.is_file() or not str(real).startswith(str(root_real) + os.sep):
            # Directories, symlinks out of the root, vanished files: skip,
            # never touch. Refused list records escape attempts.
            if str(real).startswith(str(root_real) + os.sep):
                report.skipped.append(rel)
            else:
                report.refused.append(rel)
            continue
        category = classify(entry)
        try:
            dest = _safe_destination(root, category, entry.name)
        except RefusedPath:
            report.refused.append(rel)
            continue
        size = entry.stat().st_size
        digest = _sha256(entry)
        move = TriageMove(
            source=rel,
            destination=str(dest.relative_to(root)),
            category=category,
            size_bytes=size,
            sha256=digest,
        )
        if dry_run:
            report.moved.append(move)
            continue
        os.rename(entry, dest)  # same filesystem: atomic move, no copy-delete
        _ledger_append(root, move)
        report.moved.append(move)
    return report


def read_ledger(inbox: str | Path) -> List[Dict]:
    """Read the move ledger (provenance — law 1 made queryable)."""
    ledger = Path(inbox) / LEDGER_DIR / LEDGER_FILE
    if not ledger.exists():
        return []
    records = []
    with open(ledger, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
