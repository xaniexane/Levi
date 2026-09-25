"""Reward ledger — append-only, hash-chained.

Mirrors the money layer's honesty posture (levi.monetize.ledger):
every earn/burn/expire is one JSON object per line under
``~/.levi/rewards/rewards.jsonl`` (dir 0o700, file 0o600). Each entry
carries ``prev`` (the previous entry's hash) and ``hash`` (SHA-256 over
the canonical entry), so tampering breaks the chain and
:func:`verify` reports it.

Entry event kinds:
  earn    a rule fired on a real backing event — value granted
  burn    a granted benefit was redeemed/consumed
  expire  a month-scoped benefit lapsed at month end

Every earn cites its ``basis_ref`` — the backing income event or usage
report. An earn without a basis_ref is refused: the ledger never
invents value.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

EVENT_KINDS = ("earn", "burn", "expire")

GENESIS_PREV = "0" * 64


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rewards_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".levi" / "rewards"


def ledger_path(home: Optional[Path] = None) -> Path:
    return rewards_dir(home) / "rewards.jsonl"


def _canonical(entry: Dict[str, Any]) -> bytes:
    return json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _hash_entry(entry: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(entry)).hexdigest()


def read(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read all ledger entries oldest-first. Corrupt lines are skipped."""
    path = ledger_path(home)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def verify(home: Optional[Path] = None) -> Dict[str, Any]:
    """Verify the hash chain. Returns {"ok", "entries", "first_bad_seq"}. """
    entries = read(home)
    prev = GENESIS_PREV
    for i, entry in enumerate(entries):
        expect_prev = entry.get("prev")
        body = {k: v for k, v in entry.items() if k != "hash"}
        if expect_prev != prev:
            return {"ok": False, "entries": len(entries), "first_bad_seq": entry.get("seq", i)}
        if entry.get("hash") != _hash_entry(body):
            return {"ok": False, "entries": len(entries), "first_bad_seq": entry.get("seq", i)}
        if entry.get("seq") != i:
            return {"ok": False, "entries": len(entries), "first_bad_seq": entry.get("seq", i)}
        prev = entry["hash"]
    return {"ok": True, "entries": len(entries), "first_bad_seq": None}


def append(
    event: str,
    account: str,
    reward_type: str,
    reward_id: str,
    detail: Dict[str, Any],
    *,
    basis_ref: Optional[Dict[str, Any]] = None,
    rule_id: str = "",
    at: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one ledger entry and return it.

    earn entries REQUIRE basis_ref ({"kind": "income_event"|"usage_report",
    "id": ...}) — refused otherwise. burn/expire entries reference the
    earn they settle via detail["settles"] (informational).
    """
    if event not in EVENT_KINDS:
        raise ValueError(f"event must be one of {EVENT_KINDS}, got {event!r}")
    if not account or not isinstance(account, str):
        raise ValueError("account must be a non-empty string")
    if event == "earn" and not basis_ref:
        raise ValueError("earn entries require a basis_ref — the ledger never invents value")
    if event == "earn" and not rule_id:
        raise ValueError("earn entries require the rule_id that fired")

    path = ledger_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)

    entries = read(home)
    prev = entries[-1]["hash"] if entries else GENESIS_PREV
    entry = {
        "seq": len(entries),
        "id": uuid.uuid4().hex[:12],
        "at": at or _utcnow(),
        "account": account,
        "event": event,
        "rule_id": rule_id,
        "reward_type": reward_type,
        "reward_id": reward_id,
        "detail": detail or {},
        "basis_ref": basis_ref,
        "prev": prev,
    }
    entry["hash"] = _hash_entry(entry)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)
    return entry


def earns_for(
    account: str,
    rule_id: Optional[str] = None,
    home: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Earn entries for an account, optionally filtered to one rule."""
    return [
        e
        for e in read(home)
        if e.get("event") == "earn"
        and e.get("account") == account
        and (rule_id is None or e.get("rule_id") == rule_id)
    ]


def has_earn_for_basis(
    account: str, rule_id: str, basis_id: str, home: Optional[Path] = None
) -> bool:
    """True if this rule already fired for this account on this backing event."""
    return any(
        (e.get("basis_ref") or {}).get("id") == basis_id
        for e in earns_for(account, rule_id, home)
    )
