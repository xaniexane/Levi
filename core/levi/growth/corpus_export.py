"""Export growth learnings as a redacted training-signal corpus.

``export_corpus(out, ...)`` writes JSONL — one record per self-taught
learning — that the curriculum builder can ingest as future training
signal (the SCAFFOLD brain's ``prepare_corpus`` ingests ``{"text": …}``
records; this export is the adapter between what the growth loop
learns and what the brain trains on).

Schema (one JSON object per line):

    {
      "text": "<redacted learning text>",   # secrets/PII-shaped strings scrubbed
      "kind": "fact|preference|procedural|correction",
      "confidence": 0.0-1.0,
      "corroborated_count": <int>,
      "source": "growth",
      "status": "provisional",
      "cycle_id": "<cycle that taught it>",
      "memory_id": "<memory entry id>"
    }

Properties:

* **redacted** — every text passes through
  :func:`levi.growth.redact.redact_text` (best-effort; the loop's own
  learnings stay local-first, this is belt-and-braces for a corpus
  that may travel);
* **deduped** — exact duplicates collapse by content hash;
* **deterministic** — records sorted by ``memory_id`` so exports diff
  cleanly;
* **learnings only** — distribution routing slips and curriculum seed
  are excluded (the ``levi-learned`` tag is the marker);
* **append-only friendly** — re-exports are idempotent snapshots; the
  consumer can diff on ``memory_id``.

Raises ValueError on bad arguments.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from levi.growth.redact import redact_text

try:
    from levi.memory.store import MemoryStore
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore

_WS = re.compile(r"\s+")
_LEARNING_KINDS = ("fact", "preference", "procedural", "correction")


def _learning_kind(tags: list[str]) -> str | None:
    for kind in _LEARNING_KINDS:
        if kind in tags:
            return kind
    return None


def _content_key(text: str) -> str:
    norm = _WS.sub(" ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def collect_corpus_records(
    store: Any = None,
    *,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """Collect redacted, deduped corpus records from growth learnings.

    Raises ValueError when ``min_confidence`` is not within 0..1.
    """
    try:
        min_confidence = float(min_confidence)
    except (TypeError, ValueError):
        raise ValueError(
            "collect_corpus_records: min_confidence must be a number, got %r"
            % (min_confidence,)
        ) from None
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError(
            "collect_corpus_records: min_confidence must be within 0..1, got %r"
            % (min_confidence,)
        )
    if MemoryStore is None:
        return []
    if store is None:
        store = MemoryStore()

    records: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    # creation order: the earliest-learned identity wins on duplicates,
    # while corroboration/confidence merge to their strongest values
    entries = sorted(
        store.list(limit=5000),
        key=lambda e: (
            str(getattr(e, "created_at", "") or ""),
            str(getattr(e, "id", "") or ""),
        ),
    )
    for entry in entries:
        tags = list(getattr(entry, "tags", []) or [])
        if "growth" not in tags or "levi-learned" not in tags:
            continue
        kind = _learning_kind(tags)
        if kind is None:
            continue
        text = (getattr(entry, "content", "") or "").strip()
        if len(text) < 12:
            continue
        md = getattr(entry, "metadata", None) or {}
        try:
            confidence = float(md.get("confidence", entry.importance))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < min_confidence:
            continue
        redacted = redact_text(text)
        key = _content_key(redacted)
        try:
            corroborated = int(md.get("corroborated_count", 0) or 0)
        except (TypeError, ValueError):
            corroborated = 0
        existing = seen.get(key)
        if existing is not None:
            # duplicate text: keep the strongest corroboration/confidence;
            # identity fields (cycle_id, memory_id, status) belong to the
            # earliest-created entry, which we see first by sort order
            existing["corroborated_count"] = max(
                existing["corroborated_count"], corroborated
            )
            existing["confidence"] = max(
                existing["confidence"], round(max(0.0, min(1.0, confidence)), 3)
            )
            continue
        record = {
            "text": redacted,
            "kind": kind,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "corroborated_count": corroborated,
            "source": "growth",
            "status": str(md.get("status", "provisional") or "provisional"),
            "cycle_id": str(md.get("cycle_id", "") or ""),
            "memory_id": str(getattr(entry, "id", "") or ""),
        }
        seen[key] = record
        records.append(record)
    records.sort(key=lambda r: r["memory_id"])
    return records


def export_corpus(
    out: str | Path,
    store: Any = None,
    *,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Write the growth corpus to ``out`` (JSONL). Returns a summary.

    ``out`` is created along with missing parent directories.
    Raises ValueError when ``out`` is empty.
    """
    if not out or not str(out).strip():
        raise ValueError("export_corpus: out must be a non-empty path")
    path = Path(str(out)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = collect_corpus_records(store, min_confidence=min_confidence)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {
        "path": str(path),
        "records": len(records),
        "min_confidence": min_confidence,
    }
