"""Indexed imagery corpus: Nanobit's storage face for upvoted imaginations.

Chauncey's build order (2026-09-22): "if correct (thumbs up) Nanobit
uses ASCII compression to store it in an indexed corpus or spreadsheet
database; the whole corpus is glyph-compressed and indexed for offline
retrieval."

This module EXTENDS Nanobit's symbiotic role
(``levi.revival.omega.nanobit``) — it does not rewrite the organ. It is
the storage face: the smallest thing in the room, quietly filing the
imagination away. Stored records are organ-tagged ``"nanobit"`` with
risk ``"low"``, per the organ's declared ceiling. The organ's own
invariants (never speaks anonymously, never acts above its ceiling,
never fakes) hold here: storage is deterministic, declared, low-risk,
and refuses loudly on any failure.

The store (all ASCII, all offline, stdlib only):

- ``records.jsonl`` — append-only JSONL, one record per line.
- ``index.json`` — inverted keyword index: ``{"tokens": {token: [ids]}}``.
- ``corpus.csv`` — the SAME index as a spreadsheet database: one row
  per record (id, ts, item, keywords, codebook version, ASCII blob).
- ``codebook.json`` — the versioned glyph codebook (see ``glyphs``).

ASCII compression (Chauncey's "asci compression"): the render text is
glyph-encoded (``levi.dream.glyphs``), zlib-compressed (level 9), then
base64-armored — pure ASCII, safe to paste into any spreadsheet cell.
Decoding is the exact inverse; retrieval decodes transparently.

INVARIANTS (declared, guarded in code, proven in tests):

1. "Every stored record decodes byte-identical" — ascii_blob ->
   base64 -> zlib -> glyph-decode == the original render_text. The
   store self-verifies before writing and refuses on mismatch.
2. "The inverted index always covers every stored record" — every
   keyword of every stored record maps to that record's id.
3. "Storage is append-only and owner-only" — records grow by append;
   the corpus dir is 0700 and its files 0600 (same discipline as the
   dream journal).
4. "The glyph codebook is the only decode key" — every record carries
   its codebook version; old versions are kept beside the corpus.

PROOF (honest): property tests over the invariants in
``tests/test_dream_imagine.py``, not a formal proof.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dream import glyphs
from levi.dream.journal import enforce_owner_only

__all__ = [
    "ascii_compress",
    "ascii_decompress",
    "store_upvoted",
    "retrieve",
    "list_records",
    "index_coverage_ok",
]

ORGAN = "nanobit"
_RISK = "low"

RECORDS_FILE = "records.jsonl"
INDEX_FILE = "index.json"
CSV_FILE = "corpus.csv"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ensure_corpus_dir(corpus_dir: "str | Path") -> Path:
    path = Path(corpus_dir)
    path.mkdir(parents=True, exist_ok=True)
    # owner-only discipline, same as the dream journal
    try:
        import os

        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def ascii_compress(text: str, codebook: Optional[Dict[str, object]] = None) -> str:
    """Glyph-encode -> zlib -> base64. Pure ASCII out (spreadsheet-safe)."""
    if not isinstance(text, str):
        raise TypeError("ascii_compress: text must be str")
    glyph_text = glyphs.encode(text, codebook)
    blob = zlib.compress(glyph_text.encode("utf-8"), 9)
    return base64.b64encode(blob).decode("ascii")


def ascii_decompress(
    blob: str, codebook: Optional[Dict[str, object]] = None
) -> str:
    """Exact inverse of :func:`ascii_compress`."""
    if not isinstance(blob, str):
        raise TypeError("ascii_decompress: blob must be str")
    glyph_text = zlib.decompress(base64.b64decode(blob.encode("ascii"))).decode(
        "utf-8"
    )
    return glyphs.decode(glyph_text, codebook)


def _record_id(turn_ref: str, feedback_ref: str) -> str:
    return "img-" + hashlib.sha256(
        ("%s::%s" % (turn_ref, feedback_ref)).encode("utf-8")
    ).hexdigest()[:12]


def _records_path(d: Path) -> Path:
    return d / RECORDS_FILE


def _index_path(d: Path) -> Path:
    return d / INDEX_FILE


def _csv_path(d: Path) -> Path:
    return d / CSV_FILE


def _read_records(d: Path) -> List[Dict[str, Any]]:
    path = _records_path(d)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate, never crash the corpus
        if isinstance(row, dict):
            out.append(row)
    return out


def _write_index(d: Path, records: List[Dict[str, Any]]) -> None:
    """Rebuild the inverted index from ALL records (coverage by construction)."""
    tokens: Dict[str, List[str]] = {}
    for rec in records:
        rid = rec.get("id", "")
        for token in rec.get("keywords", []) or []:
            token = str(token)
            ids = tokens.setdefault(token, [])
            if rid and rid not in ids:
                ids.append(rid)
    for ids in tokens.values():
        ids.sort()
    payload = {"tokens": tokens, "record_count": len(records)}
    path = _index_path(d)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    enforce_owner_only(path)


def _write_csv(d: Path, records: List[Dict[str, Any]]) -> None:
    """Rewrite the spreadsheet database from ALL records (same source)."""
    path = _csv_path(d)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "ts", "item", "turn_ref", "feedback_ref", "keywords",
         "codebook_version", "organ", "ascii_blob"]
    )
    for rec in sorted(records, key=lambda r: str(r.get("id", ""))):
        writer.writerow(
            [
                rec.get("id", ""),
                rec.get("ts", ""),
                rec.get("item", ""),
                rec.get("turn_ref", ""),
                rec.get("feedback_ref", ""),
                ";".join(rec.get("keywords", []) or []),
                rec.get("codebook_version", ""),
                rec.get("organ", ""),
                rec.get("ascii_blob", ""),
            ]
        )
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    enforce_owner_only(path)


def store_upvoted(
    render: Dict[str, Any], feedback_ref: str, corpus_dir: "str | Path"
) -> str:
    """Store a thumbs-up'd imagination — Nanobit's storage face.

    ``render`` is an ``imagine_vivid`` record; ``feedback_ref`` is the
    feedback id that approved it (thumbs-up). The render text is
    glyph-compressed, zlib-compressed, ASCII-armored, and filed in the
    indexed corpus + spreadsheet export.

    Loud refusal (never silent): invalid render, empty feedback ref,
    or a failed self-verification round-trip all raise.
    """
    if not isinstance(render, dict) or not render.get("render_text"):
        raise ValueError("store_upvoted: render must be an imagine_vivid record")
    if not isinstance(feedback_ref, str) or not feedback_ref.strip():
        raise ValueError("store_upvoted: feedback_ref must be non-empty "
                         "(thumbs-up stores only with its feedback linked)")

    d = _ensure_corpus_dir(corpus_dir)
    glyphs.write_codebook(d)
    codebook = glyphs.load_codebook(d)  # current version

    render_text = render["render_text"]
    blob = ascii_compress(render_text, codebook)

    # self-verification BEFORE writing: byte-identical or refuse
    if ascii_decompress(blob, codebook) != render_text:
        raise RuntimeError("store_upvoted: self-verification failed — "
                           "round-trip mismatch, refusing to store")

    record = {
        "id": _record_id(str(render.get("turn_ref", "")), feedback_ref),
        "ts": _now_iso(),
        "item": render.get("item", ""),
        "turn_ref": render.get("turn_ref", ""),
        "feedback_ref": feedback_ref,
        "organ": ORGAN,
        "risk": _RISK,
        "keywords": list(render.get("keywords", []) or []),
        "codebook_version": codebook["version"],
        "ascii_blob": blob,
        "glyph_stats": glyphs.compression_stats(render_text, codebook),
        "render_bytes": len(render_text.encode("utf-8")),
        "blob_chars": len(blob),
    }

    records = _read_records(d)
    if any(r.get("id") == record["id"] for r in records):
        # idempotent re-store of the same (turn, feedback): no duplicate
        return record["id"]
    records.append(record)

    path = _records_path(d)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    enforce_owner_only(path)

    _write_index(d, records)
    _write_csv(d, records)
    return record["id"]


def list_records(corpus_dir: "str | Path") -> List[Dict[str, Any]]:
    """All stored records (metadata only — use retrieve for decoded text)."""
    d = _ensure_corpus_dir(corpus_dir)
    return _read_records(d)


def index_coverage_ok(corpus_dir: "str | Path") -> Dict[str, Any]:
    """Verify invariant 2: every record's keywords resolve to that record."""
    d = _ensure_corpus_dir(corpus_dir)
    records = _read_records(d)
    index_path = _index_path(d)
    tokens: Dict[str, List[str]] = {}
    if index_path.exists():
        try:
            tokens = json.loads(index_path.read_text(encoding="utf-8")).get(
                "tokens", {}
            )
        except (OSError, json.JSONDecodeError):
            tokens = {}
    missing: List[Dict[str, str]] = []
    for rec in records:
        for token in rec.get("keywords", []) or []:
            if rec.get("id") not in tokens.get(str(token), []):
                missing.append({"record": rec.get("id", ""), "token": str(token)})
    return {
        "records": len(records),
        "indexed_tokens": len(tokens),
        "missing": missing,
        "ok": not missing,
    }


def retrieve(
    query: str, corpus_dir: "str | Path", limit: int = 10
) -> List[Dict[str, Any]]:
    """Offline retrieval: rank records by keyword overlap with the query.

    No network, no imports beyond stdlib. Decodes each hit's ASCII blob
    transparently (base64 -> zlib -> glyph-decode) with the record's own
    codebook version.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("retrieve: query must be a non-empty string")
    if limit < 1:
        raise ValueError("retrieve: limit must be >= 1")

    d = _ensure_corpus_dir(corpus_dir)
    records = _read_records(d)
    if not records:
        return []

    import re as _re

    qtokens = set(_re.findall(r"[a-z0-9]+", query.lower()))
    scored: List[tuple] = []
    for rec in records:
        kws = {str(k).lower() for k in rec.get("keywords", []) or []}
        hits = qtokens & kws
        if hits:
            scored.append((len(hits), str(rec.get("id", "")), rec))
    scored.sort(key=lambda t: (-t[0], t[1]))

    out: List[Dict[str, Any]] = []
    for score, _rid, rec in scored[:limit]:
        codebook = glyphs.load_codebook(d, rec.get("codebook_version"))
        text = ascii_decompress(rec["ascii_blob"], codebook)
        out.append(
            {
                "id": rec.get("id"),
                "item": rec.get("item"),
                "turn_ref": rec.get("turn_ref"),
                "score": score,
                "keywords": rec.get("keywords", []),
                "text": text,
            }
        )
    return out
