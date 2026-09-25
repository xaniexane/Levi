"""Ingest text/markdown files into the memory store as RAG chunks.

Each chunk becomes a SEMANTIC memory entry tagged ``rag`` with provenance
metadata. Fail-closed: unreadable files are counted as skipped, never
raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from levi.memory.types import MemoryType

from .chunking import chunk_text


@dataclass
class IngestReport:
    files_ingested: int = 0
    files_skipped: int = 0
    chunks: int = 0
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return "ingested %d file(s) → %d chunk(s), skipped %d file(s)%s" % (
            self.files_ingested,
            self.chunks,
            self.files_skipped,
            (" (%s)" % ", ".join(self.skipped_files)) if self.skipped_files else "",
        )


def _read_text(path: Path) -> Optional[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def ingest_file(
    path,
    store,
    source_doc: Optional[str] = None,
    max_chars: int = 500,
    overlap: int = 100,
    tags: Optional[List[str]] = None,
    importance: float = 0.6,
) -> IngestReport:
    """Ingest one file. Returns a report; never raises on bad files."""
    report = IngestReport()
    try:
        p = Path(path)
    except (TypeError, ValueError):
        report.files_skipped += 1
        report.skipped_files.append(str(path))
        report.errors.append("not a valid path: %r" % (path,))
        return report
    if not p.is_file():
        report.files_skipped += 1
        report.skipped_files.append(str(p))
        report.errors.append("not a file: %s" % p)
        return report
    text = _read_text(p)
    if text is None or not text.strip():
        report.files_skipped += 1
        report.skipped_files.append(str(p))
        report.errors.append("unreadable or empty: %s" % p)
        return report

    doc = source_doc or p.name
    try:
        chunks = chunk_text(text, doc, max_chars=max_chars, overlap=overlap)
    except ValueError as exc:
        report.files_skipped += 1
        report.skipped_files.append(str(p))
        report.errors.append("chunking failed for %s: %s" % (p, exc))
        return report

    entry_tags = ["rag"]
    if tags:
        entry_tags.extend(t for t in tags if isinstance(t, str))
    try:
        for chunk in chunks:
            metadata: Dict = {
                "rag": True,
                "provenance": chunk.to_provenance(),
            }
            store.add(
                MemoryType.SEMANTIC,
                chunk.text,
                importance=importance,
                source="rag-ingest",
                tags=entry_tags,
                metadata=metadata,
            )
    except Exception as exc:  # store failure: fail closed, report it
        report.files_skipped += 1
        report.skipped_files.append(str(p))
        report.errors.append("store.add failed for %s: %s" % (p, exc))
        return report

    report.files_ingested += 1
    report.chunks += len(chunks)
    return report


def ingest_directory(
    directory, store, pattern: str = "*.md", recursive: bool = True, **kwargs
) -> IngestReport:
    """Ingest every matching file under *directory*."""
    total = IngestReport()
    try:
        d = Path(directory)
        files = sorted(d.rglob(pattern) if recursive else d.glob(pattern))
    except (TypeError, ValueError, OSError):
        total.errors.append("bad directory: %r" % (directory,))
        return total
    for f in files:
        if f.is_file():
            rep = ingest_file(f, store, **kwargs)
            total.files_ingested += rep.files_ingested
            total.files_skipped += rep.files_skipped
            total.chunks += rep.chunks
            total.skipped_files.extend(rep.skipped_files)
            total.errors.extend(rep.errors)
    return total
