"""Receipt-chained delivery — every pipeline stage seals its proof.

The legion service standard runs analyze → quote → deliver → paid →
showcase. This module hangs a sealed receipt off every stage: each
receipt embeds the SHA-256 of the previous receipt's envelope, so the
chain is tamper-evident end to end. A client holding the chain head
can verify the entire delivery history — every stage's payload hash,
every link — with :func:`verify_chain`.

Receipts live at ``<LEVI_HOME>/neighboros/receipt_chains/<offering_id>.jsonl``,
owner-only. Each receipt payload is additionally Veil-sealed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.neighboros import _seal

STAGES = ("analyzed", "quoted", "delivering", "delivered", "paid", "showcased")
GENESIS = "GENESIS"


def _chains_dir(home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "receipt_chains"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _chain_path(offering_id: str, home: Optional[Path] = None) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in offering_id)
    return _chains_dir(home) / f"{safe}.jsonl"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _sha(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _append(path: Path, record: Dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    if not path.exists():
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.close(fd)
    else:
        os.chmod(path, 0o600)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def emit_receipt(offering_id: str, stage: str, payload: Dict[str, Any],
                 home: Optional[Path] = None,
                 now: Optional[float] = None) -> Dict[str, Any]:
    """Seal and append a receipt for one pipeline stage."""
    if not offering_id or not offering_id.strip():
        raise ValueError("offering_id must be non-empty")
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}, got {stage!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    path = _chain_path(offering_id, home)
    prev_records = read_chain(offering_id, home)
    prev = prev_records[-1]["envelope_sha"] if prev_records else GENESIS
    receipt_id = uuid.uuid4().hex[:12]
    receipt = {
        "receipt_id": receipt_id,
        "offering_id": offering_id,
        "stage": stage,
        "payload_sha256": _sha(payload),
        "prev": prev,
        "emitted_at": _utcnow(now),
    }
    context = f"neighboros-chain:{offering_id}:{receipt_id}"
    envelope = _seal.seal_dict(receipt, context, home)
    record = {"receipt": receipt, "envelope": envelope,
              "envelope_sha": _sha(envelope), "context": context}
    _append(path, record)
    return {"receipt_id": receipt_id, "offering_id": offering_id, "stage": stage,
            "prev": prev, "sealed": True}


def read_chain(offering_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _chain_path(offering_id, home)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def verify_chain(offering_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Verify every envelope and every link. Reports breaks; never raises on data."""
    records = read_chain(offering_id, home)
    breaks: List[Dict[str, Any]] = []
    prev_sha = GENESIS
    prev_stage_idx = -1
    for i, record in enumerate(records):
        receipt = record.get("receipt", {})
        context = record.get("context", "")
        try:
            opened = _seal.open_dict(record["envelope"], context, home)
        except _seal.SealError as exc:
            breaks.append({"index": i, "kind": "tampered_envelope", "detail": str(exc)})
            continue
        if opened != receipt:
            breaks.append({"index": i, "kind": "payload_mismatch",
                           "detail": "opened payload differs from stored receipt"})
        if receipt.get("prev") != prev_sha:
            breaks.append({"index": i, "kind": "broken_link",
                           "detail": f"prev {receipt.get('prev')!r} != {prev_sha!r}"})
        stage = receipt.get("stage")
        stage_idx = STAGES.index(stage) if stage in STAGES else -1
        if stage_idx < prev_stage_idx:
            breaks.append({"index": i, "kind": "stage_regression",
                           "detail": f"stage {stage!r} moved backwards"})
        prev_stage_idx = max(prev_stage_idx, stage_idx)
        prev_sha = record.get("envelope_sha", "")
        if prev_sha != _sha(record["envelope"]):
            breaks.append({"index": i, "kind": "envelope_sha_mismatch",
                           "detail": "stored envelope hash does not match envelope"})
            prev_sha = _sha(record["envelope"])
    return {"offering_id": offering_id, "ok": not breaks,
            "count": len(records), "breaks": breaks}
