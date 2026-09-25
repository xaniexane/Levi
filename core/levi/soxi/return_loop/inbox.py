"""Inbox intake for returned lesson/answer batches (R5).

Drop a ``.jsonl`` batch file into ``inbox/`` (plus an optional
``.manifest.json`` sidecar). ``intake()`` records an arrival receipt
(hash-chained, arrivals.jsonl), copies the batch byte-for-byte into
``raw/`` (immutable originals — R2), and files the batch as READY for
verification. Files that cannot be read at intake are quarantined
immediately with reasons.

Malformed CONTENT is quarantined later at verification; intake only
moves bytes and records facts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .common import (
    FRAMES,
    append_receipt,
    base_dir,
    check_batch_id,
    read_chain,
    utcnow,
)


def inbox_dir(base: Path | None = None) -> Path:
    return (base or base_dir()) / "inbox"


def raw_dir(base: Path | None = None) -> Path:
    return (base or base_dir()) / "raw"


def arrivals_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "arrivals.jsonl"


def quarantine_dir(base: Path | None = None) -> Path:
    return (base or base_dir()) / "quarantine"


def _read_manifest(jsonl_path: Path) -> dict[str, Any]:
    sidecar = jsonl_path.with_suffix(".manifest.json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def _fresh_batch_id() -> str:
    return "batch-" + utcnow().replace(":", "").replace("+", "z")


def intake(jsonl_path: str | Path, base: Path | None = None) -> dict[str, Any]:
    """Take a batch file into the inbox.

    Copies the file to inbox/ (if not already there), records a chained
    arrival receipt, and copies it byte-for-byte to raw/ as the
    immutable original (R2). Returns the receipt.
    """
    base = base or base_dir()
    src = Path(jsonl_path)
    if not src.exists() or not src.is_file():
        raise ValueError("intake: batch file not found: %s" % src)
    if src.suffix.lower() != ".jsonl":
        raise ValueError("intake: only .jsonl batches are accepted")

    inbox = inbox_dir(base)
    dest = inbox / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    manifest = _read_manifest(src)
    batch_id = check_batch_id(
        str(manifest.get("batch_id") or dest.stem or _fresh_batch_id())
    )
    raw_path = raw_dir(base) / (batch_id + ".jsonl")
    if not raw_path.exists():
        shutil.copy2(dest, raw_path)  # immutable from here on (R2)

    rec = append_receipt(
        arrivals_path(base),
        {
            "ts": utcnow(),
            "batch_id": batch_id,
            "teacher": manifest.get("teacher", "grok"),
            "persona_frames": manifest.get(
                "persona_frames", sorted(set(f for f in FRAMES))
            ),
            "date_from": manifest.get("date_from"),
            "date_to": manifest.get("date_to"),
            "batch_file": dest.name,
            "raw_file": raw_path.name,
            "bytes": dest.stat().st_size,
        },
    )
    return rec


def ready_batches(base: Path | None = None) -> list[dict[str, Any]]:
    """Arrival receipts whose batches have no verdict yet."""
    base = base or base_dir()
    verdicts = {
        r.get("batch_id") for r in read_chain(base / "verdicts.jsonl")
    }
    return [r for r in read_chain(arrivals_path(base))
            if r.get("batch_id") not in verdicts]
