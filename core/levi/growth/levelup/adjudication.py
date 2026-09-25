"""Hash-chained adjudication ledger (L13, L14).

Penalties, reversals, ability unlocks/revokes, and super-token
grants/confiscations all land here as chained receipts — one ledger,
many kinds, every action evidenced. Nothing is ever deleted: a
revocation is a new receipt that marks an earlier one REVOKED; a
reversal is a new receipt that restores it. The record survives both
ways (nothing-thrown-away law).

Super-token canon (Chauncey, 2026-09-22): earned super-power tokens
stack indefinitely; base weekly tokens do NOT stack and are NEVER
confiscated. The earned pool = token-grant receipts minus
token-confiscate receipts; base is informational only.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .receipts import GENESIS_PREV, check_entity

KINDS = (
    "penalty",           # confiscated EXP + revokes + token confiscation
    "penalty-reversal",  # Chauncey-approved undo of a penalty
    "unlock",            # ability unlocked (level requirement met)
    "unlock-revoke",     # ability revoked by penalty
    "unlock-restore",    # revoked ability re-granted by reversal
    "token-grant",       # super tokens added to the EARNED pool
    "token-base",        # base weekly allotment (informational; never confiscated)
    "token-confiscate",  # super tokens removed from the EARNED pool by penalty
)


def adjudication_dir() -> Path:
    override = os.environ.get("LEVI_LEVELUP_DIR")
    p = (Path(override).expanduser() if override
         else Path.home() / ".levi" / "growth" / "levelup")
    p.mkdir(parents=True, exist_ok=True)
    return p


def adjudication_path() -> Path:
    return adjudication_dir() / "adjudication_ledger.jsonl"


def _utcnow() -> str:
    from datetime import datetime, timezone

    # microsecond precision: penalty spans anchor token confiscation on
    # receipt order, and same-second collisions would sweep honestly
    # earned tokens into the confiscation span.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _canonical(rec: dict) -> bytes:
    body = {k: v for k, v in rec.items() if k != "hash"}
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _hash_receipt(rec: dict) -> str:
    return hashlib.sha256(_canonical(rec)).hexdigest()


def read_adj(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or adjudication_path()
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


def verify_adj(path: Path | None = None) -> tuple[bool, list[str]]:
    """Same chain discipline as the EXP ledger (L2 style): fail-closed."""
    receipts = read_adj(path)
    errors: list[str] = []
    prev_hash = GENESIS_PREV
    for i, rec in enumerate(receipts):
        if rec.get("seq") != i + 1:
            errors.append(f"adj receipt {i}: seq {rec.get('seq')} != {i + 1}")
        if rec.get("prev_hash") != prev_hash:
            errors.append(f"adj receipt {i}: prev_hash linkage broken")
        if _hash_receipt(rec) != rec.get("hash"):
            errors.append(f"adj receipt {i}: hash mismatch (tampered)")
        prev_hash = rec.get("hash", "")
        if not isinstance(prev_hash, str) or len(prev_hash) != 64:
            errors.append(f"adj receipt {i}: malformed hash")
            prev_hash = GENESIS_PREV
    return (not errors), errors


def append_adj(
    kind: str,
    entity: str,
    data: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    """Append one adjudication receipt. Chain must verify first (fail-closed)."""
    check_entity(entity)
    if kind not in KINDS:
        raise ValueError("append_adj: unknown kind %r" % (kind,))
    path = path or adjudication_path()
    receipts = read_adj(path)
    ok, errors = verify_adj(path)
    if not ok:
        raise ValueError(
            "append_adj: adjudication chain broken, halted: %s" % "; ".join(errors)
        )
    prev_hash = receipts[-1]["hash"] if receipts else GENESIS_PREV
    rec: dict[str, Any] = {
        "seq": len(receipts) + 1,
        "ts": _utcnow(),
        "entity": entity,
        "kind": kind,
        "prev_hash": prev_hash,
        "data": dict(data),
    }
    rec["hash"] = _hash_receipt(rec)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ---------------------------------------------------------------------------
# Derived state (always recomputed from receipts — same discipline as L1)
# ---------------------------------------------------------------------------


def active_penalties(entity: str, path: Path | None = None) -> list[dict]:
    """Penalty receipts not undone by a later penalty-reversal."""
    check_entity(entity)
    reversed_ids = {
        r["data"].get("penalty_seq")
        for r in read_adj(path)
        if r.get("entity") == entity and r.get("kind") == "penalty-reversal"
    }
    return [
        r
        for r in read_adj(path)
        if r.get("entity") == entity
        and r.get("kind") == "penalty"
        and r.get("seq") not in reversed_ids
    ]


def confiscated_exp(entity: str, path: Path | None = None) -> int:
    """Total EXP confiscated by active penalties."""
    return sum(int(r["data"].get("confiscated_exp", 0))
               for r in active_penalties(entity, path))


def earned_tokens(entity: str, path: Path | None = None) -> int:
    """EARNED super-token balance: grants minus confiscations. Never base."""
    check_entity(entity)
    bal = 0
    for r in read_adj(path):
        if r.get("entity") != entity:
            continue
        if r.get("kind") == "token-grant":
            bal += int(r["data"].get("tokens", 0))
        elif r.get("kind") == "token-confiscate":
            bal -= int(r["data"].get("tokens", 0))
    return max(bal, 0)


def active_abilities(entity: str, path: Path | None = None) -> list[str]:
    """Ability ids currently active: unlocked, not revoked (or restored)."""
    check_entity(entity)
    active: list[str] = []
    for r in read_adj(path):
        if r.get("entity") != entity:
            continue
        aid = r["data"].get("ability_id")
        if r.get("kind") == "unlock" and aid not in active:
            active.append(aid)
        elif r.get("kind") in ("unlock-revoke",) and aid in active:
            active.remove(aid)
        elif r.get("kind") == "unlock-restore" and aid not in active:
            active.append(aid)
    return active
