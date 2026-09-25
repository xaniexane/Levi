"""Sealed skill receipts — finish well = receipt.

Every finished academy module mints a tamper-evident, Veil-sealed
receipt: verifiable proof of skill, not a badge you screenshot.
The payload is sealed with the academy keeper key; any tampering
with the stored record fails verification loudly.

Receipts live at ``<LEVI_HOME>/academy/differentiators/receipts/``,
owner-only (0700 dir, 0600 files).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import _seal


def _receipts_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "receipts" / learner_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def mint_receipt(
    learner_id: str,
    module_id: str,
    score: float,
    rubric: List[Dict[str, Any]],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Mint a sealed skill receipt for a finished module."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not module_id or not module_id.strip():
        raise ValueError("module_id must be non-empty")
    score = float(score)
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"score must be 0..1, got {score}")
    if not rubric or not isinstance(rubric, list):
        raise ValueError("rubric must be a non-empty list")
    checks = []
    for i, item in enumerate(rubric):
        if not isinstance(item, dict) or "name" not in item:
            raise ValueError(f"rubric[{i}] needs a 'name'")
        checks.append({"name": str(item["name"]), "passed": bool(item.get("passed", False))})
    receipt_id = uuid.uuid4().hex[:12]
    payload = {
        "receipt_id": receipt_id,
        "learner_id": learner_id,
        "module_id": module_id,
        "score": round(score, 3),
        "rubric": checks,
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks_total": len(checks),
        "minted_at": _utcnow(now),
    }
    context = f"academy-receipt:{learner_id}:{receipt_id}"
    envelope = _seal.seal_dict(payload, context, home)
    record = {"payload": payload, "envelope": envelope}
    _write_json(_receipts_dir(learner_id, home) / f"{receipt_id}.json", record)
    return {"receipt_id": receipt_id, "learner_id": learner_id, "module_id": module_id,
            "score": payload["score"], "sealed": True}


def verify_receipt(learner_id: str, receipt_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Verify a receipt. Raises SealError on tampering; KeyError if unknown."""
    path = _receipts_dir(learner_id, home) / f"{receipt_id}.json"
    if not path.exists():
        raise KeyError(f"unknown receipt {receipt_id!r} for learner {learner_id!r}")
    record = json.loads(path.read_text(encoding="utf-8"))
    context = f"academy-receipt:{learner_id}:{receipt_id}"
    payload = _seal.open_dict(record["envelope"], context, home)
    if payload != record["payload"]:
        raise _seal.SealError("receipt payload does not match its sealed envelope")
    return payload


def list_receipts(learner_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List receipt payloads for a learner (verified on read)."""
    out = []
    d = _receipts_dir(learner_id, home)
    for path in sorted(d.glob("*.json")):
        try:
            out.append(verify_receipt(learner_id, path.stem, home))
        except _seal.SealError:
            out.append({"receipt_id": path.stem, "learner_id": learner_id,
                        "tampered": True})
    return out
