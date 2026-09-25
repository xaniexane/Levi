"""Hash-chained EXP receipt ledger (L1, L2).

Every EXP award appends exactly one receipt to
``<LEVI_LEVELUP_DIR>/exp_ledger.jsonl``. Each receipt's sha256 hash
commits to the previous receipt's hash, so tampering with history is
detectable (same convention as the dynasty receipt chains — detect,
not tamper-proof, against disk access).

Receipts are per-entity: Nanobit ("nanobit") and each Legion persona
("legion:<persona>"). Totals are derived by summing deltas, never
stored as source of truth (L1).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

GENESIS_PREV = "0" * 64

_ENTITY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")


def levelup_dir() -> Path:
    """Storage dir — ``~/.levi/growth/levelup`` (override: LEVI_LEVELUP_DIR)."""
    override = os.environ.get("LEVI_LEVELUP_DIR")
    p = Path(override).expanduser() if override else (
        Path.home() / ".levi" / "growth" / "levelup"
    )
    p.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path() -> Path:
    return levelup_dir() / "exp_ledger.jsonl"


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_entity(entity: str) -> str:
    if not isinstance(entity, str) or not _ENTITY_RE.fullmatch(entity):
        raise ValueError(
            "entity must be 1-64 chars of [A-Za-z0-9_.:-], got %r" % (entity,)
        )
    return entity


def _canonical(rec: dict) -> bytes:
    """Canonical bytes for hashing: sorted keys, compact, no hash field."""
    body = {k: v for k, v in rec.items() if k != "hash"}
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _hash_receipt(rec: dict) -> str:
    return hashlib.sha256(_canonical(rec)).hexdigest()


def read_receipts(path: Path | None = None) -> list[dict[str, Any]]:
    """All receipts, oldest first (tolerates corrupt lines by skipping)."""
    path = path or ledger_path()
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def verify_chain(path: Path | None = None) -> tuple[bool, list[str]]:
    """Verify seq continuity, prev_hash linkage, and hash integrity.

    Returns (ok, errors). Empty ledger is valid (nothing to break).
    """
    receipts = read_receipts(path)
    errors: list[str] = []
    prev_hash = GENESIS_PREV
    for i, rec in enumerate(receipts):
        want_seq = i + 1
        if rec.get("seq") != want_seq:
            errors.append(f"receipt {i}: seq {rec.get('seq')} != {want_seq}")
        if rec.get("prev_hash") != prev_hash:
            errors.append(f"receipt {i}: prev_hash linkage broken")
        if _hash_receipt(rec) != rec.get("hash"):
            errors.append(f"receipt {i}: hash mismatch (tampered)")
        prev_hash = rec.get("hash", "")
        if not isinstance(prev_hash, str) or len(prev_hash) != 64:
            errors.append(f"receipt {i}: malformed hash")
            prev_hash = GENESIS_PREV
    return (not errors), errors


def award_exp(
    entity: str,
    kind: str,
    exp_delta: int,
    meta: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Award EXP: verify the chain, then append one chained receipt.

    Raises ValueError on bad inputs or a broken chain (L2: fail-closed —
    awards stop until the chain is repaired).
    """
    check_entity(entity)
    if not isinstance(kind, str) or not kind or len(kind) > 64:
        raise ValueError("award_exp: kind must be a non-empty string <= 64 chars")
    if not isinstance(exp_delta, int):
        raise ValueError(
            "award_exp: exp_delta must be an int, got %s" % type(exp_delta).__name__
        )
    if exp_delta < 0:
        raise ValueError("award_exp: exp_delta must be >= 0 (no negative EXP)")
    meta = dict(meta or {})
    path = path or ledger_path()
    receipts = read_receipts(path)
    ok, errors = verify_chain(path)
    if not ok:
        raise ValueError(
            "award_exp: ledger chain broken, awards halted: %s" % "; ".join(errors)
        )
    seq = len(receipts) + 1
    prev_hash = receipts[-1]["hash"] if receipts else GENESIS_PREV
    total = sum(int(r.get("exp_delta", 0)) for r in receipts if r.get("entity") == entity)
    rec: dict[str, Any] = {
        "seq": seq,
        "ts": _utcnow(),
        "entity": entity,
        "kind": kind,
        "exp_delta": exp_delta,
        "total_exp": total + exp_delta,
        "prev_hash": prev_hash,
        "meta": meta,
    }
    rec["hash"] = _hash_receipt(rec)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def entity_total(entity: str, path: Path | None = None) -> int:
    """Cumulative EXP for one entity — derived from receipts (L1)."""
    check_entity(entity)
    return sum(
        int(r.get("exp_delta", 0))
        for r in read_receipts(path)
        if r.get("entity") == entity
    )
