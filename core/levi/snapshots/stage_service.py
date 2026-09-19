"""Snapshots as a providable legion service.

New service type ``ops-snapshot``: a client's system / project / config
is captured into versioned, restorable, refinable artifacts — "we
snapshot it; you can roll back, fork, or improve from any stage."

Rides the standard pipeline: analyze -> quote -> deliver -> paid ->
showcase. Quotes ride the founder price advisor (quote, not a charge).
Money rides the Cybrus gateway only, through the standard paid stage.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from levi.snapshots.stages import StageSnapshot, StageStore

SNAPSHOT_SERVICE_TYPE = "ops-snapshot"
SNAPSHOT_SERVICE_BLURB = (
    "snapshot a system/project/config into versioned, restorable, refinable artifacts"
)

_CONTENT_EXTS = {".json", ".md", ".txt", ".py", ".yaml", ".yml", ".toml", ".cfg", ".ini"}
_CONTENT_LIMIT = 64 * 1024


class SnapshotServiceError(ValueError):
    """The snapshot service refused."""


def register_snapshot_service_type() -> str:
    """Add ops-snapshot to the legion service catalog. Idempotent."""
    from levi.services.offering import SERVICE_TYPES

    SERVICE_TYPES.setdefault(SNAPSHOT_SERVICE_TYPE, SNAPSHOT_SERVICE_BLURB)
    return SNAPSHOT_SERVICE_TYPE


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_subject(subject_dir: Path) -> Dict[str, Any]:
    """Honest inventory of a client subject directory.

    Small text files by content, everything else by hash + size.
    Symlinks and unreadable files are recorded as such, never followed
    into loops or invented.
    """
    root = Path(subject_dir)
    if not root.is_dir():
        raise SnapshotServiceError(f"subject is not a directory: {root}")
    files: List[Dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if "__pycache__" in p.parts or ".git" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            files.append({"path": rel, "kind": "symlink", "target": os_readlink(p)})
            continue
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
            entry: Dict[str, Any] = {"path": rel, "kind": "file", "size": size, "sha256": _sha256_file(p)}
            if p.suffix.lower() in _CONTENT_EXTS and size <= _CONTENT_LIMIT:
                try:
                    entry["content"] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
            files.append(entry)
        except OSError as exc:
            files.append({"path": rel, "kind": "unreadable", "error": str(exc)})
    return {
        "kind": "subject-inventory",
        "subject": str(root),
        "files": files,
        "file_count": len(files),
    }


def os_readlink(p: Path) -> str:
    try:
        return p.readlink().as_posix() if hasattr(p.readlink(), "as_posix") else str(p.readlink())
    except OSError:
        return "<unreadable>"


def advise_snapshot_quote(
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    founder_commission: float = 0.0,
) -> Dict[str, Any]:
    """Quoting hook: price the snapshot service via the founder price advisor.

    Returns the advice with its receipt. A QUOTE, not a charge — moves nothing.
    """
    from levi.advisor.pricing import PricePlan, advise_price

    advice = advise_price(
        PricePlan(
            tier="standard",
            giant_price=giant_price,
            strategy=strategy,
            founder_commission=founder_commission,
        )
    )
    return {
        "service_type": SNAPSHOT_SERVICE_TYPE,
        "low": advice.low,
        "high": advice.high,
        "recommended": advice.recommended,
        "rationale": advice.rationale,
        "receipt": advice.receipt,
    }


def offer_snapshot_service(
    *,
    provider: str,
    title: str,
    subject: str,
    scope: str = "",
    client: str = "",
    home: Optional[Path] = None,
):
    """Stage 1 — offer a snapshot service through the standard pipeline."""
    from levi.services.offering import offer_service

    register_snapshot_service_type()
    return offer_service(
        provider=provider,
        service_type=SNAPSHOT_SERVICE_TYPE,
        title=title,
        problem=f"snapshot subject for versioned rollback/fork/improve: {subject}",
        scope=scope,
        client=client,
        home=home,
    )


def quote_snapshot_service(
    offering,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    founder_commission: float = 0.0,
    home: Optional[Path] = None,
):
    """Stage 3 — quote via the standard pipeline + snapshot advice receipt."""
    from levi.services.offering import quote_service

    advice = advise_snapshot_quote(
        giant_price=giant_price, strategy=strategy, founder_commission=founder_commission
    )
    offering = quote_service(
        offering,
        giant_price=giant_price,
        strategy=strategy,
        founder_commission=founder_commission,
        home=home,
    )
    offering.log(
        "snapshot-quote",
        f"advisor band ${advice['low']:.2f}-${advice['high']:.2f}, "
        f"recommended ${advice['recommended']:.2f}",
    )
    from levi.services.offering import ServiceStore

    return ServiceStore(home=home).save(offering)


def deliver_snapshot_service(
    offering,
    *,
    subject_dir: Path,
    stage_label: str,
    note: str = "",
    confidence: float = 0.9,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Stage 4 — deliver: capture the subject as sealed stage snapshot(s).

    Returns the service receipt: snapshot ids, restore instructions, and
    the chain verification count. The client can roll back, fork, or
    improve from any stage.
    """
    from levi.services.offering import ServiceStore, deliver_service

    store = StageStore(home=home)
    payload = inventory_subject(subject_dir)
    snap = store.capture_stage(
        name=f"client:{offering.offering_id}:{stage_label}",
        payload=payload,
        stage_label=stage_label,
        note=note,
    )
    verified = store.verify_chain()
    solution = (
        f"Subject captured as sealed stage snapshot {snap.id} "
        f"(stage '{stage_label}', {payload['file_count']} files inventoried). "
        f"Roll back with: levi snapshot restore {snap.id} <target-dir>. "
        f"Fork-and-improve with: levi snapshot fork {snap.id} <name>."
    )
    evidence = [
        f"snapshot_id={snap.id}",
        f"payload_hash={snap.payload_hash}",
        f"chain_verified={verified}",
        f"files={payload['file_count']}",
    ]
    deliver_service(
        offering,
        solution=solution,
        evidence=evidence,
        confidence=confidence,
        verification=f"seal + hash-chain verified over {verified} snapshot(s)",
        home=home,
    )
    receipt = {
        "offering_id": offering.offering_id,
        "service_type": SNAPSHOT_SERVICE_TYPE,
        "snapshot_id": snap.id,
        "stage_label": stage_label,
        "payload_hash": snap.payload_hash,
        "chain_verified": verified,
        "restore": f"levi snapshot restore {snap.id} <target-dir>",
        "fork": f"levi snapshot fork {snap.id} <name>",
    }
    offering.log("snapshot-receipt", json.dumps(receipt, sort_keys=True))
    ServiceStore(home=home).save(offering)
    return receipt
