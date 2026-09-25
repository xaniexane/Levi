"""Cloud-sync staging + cadence (R7).

This builds the SYNC PACKAGE the cloud side consumes:

    sync/outbox/soxi-sync-<ts>/
        manifest.json       — package id, created_ts, cadence_days,
                              base vector, package vector, receipt heads
        deltas.jsonl        — new/updated lessons since the last package
        receipts.jsonl      — the chained receipts behind those deltas
        version_vector.json — chain lengths: arrivals/verdicts/
                              refinements/promotions

The cloud backend itself is NOT built here — this package is the
interface contract. Next build: the cloud endpoint that accepts this
package, applies deltas idempotently on version vectors, and fans out
to every connected client so the collective intelligence updates.

Cadence: Chauncey's dial. Default 3 days ("maybe 2-3 days is good").
Daily is a one-line config flip (config.json: {"cadence_days": 1}).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .common import append_receipt, base_dir, read_chain, utcnow
from .promote import store_path

DEFAULT_CADENCE_DAYS = 3


def config_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "config.json"


def get_config(base: Path | None = None) -> dict[str, Any]:
    base = base or base_dir()
    try:
        cfg = json.loads(config_path(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("cadence_days", DEFAULT_CADENCE_DAYS)
    return cfg


def set_cadence_days(days: int, base: Path | None = None) -> dict[str, Any]:
    """Chauncey's dial: flip the sync cadence (e.g. 1 for daily)."""
    if not isinstance(days, int) or days < 1:
        raise ValueError("cadence must be a positive integer of days")
    base = base or base_dir()
    cfg = get_config(base)
    cfg["cadence_days"] = days
    config_path(base).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def version_vector_path(base: Path | None = None) -> Path:
    return (base or base_dir()) / "sync" / "version_vector.json"


def version_vector(base: Path | None = None) -> dict[str, int]:
    """Chain lengths = the store's version vector."""
    base = base or base_dir()
    vv: dict[str, int] = {}
    for name in ("arrivals", "verdicts", "refinements", "promotions"):
        vv[name] = len(read_chain(base / (name + ".jsonl")))
    return vv


def last_package(base: Path | None = None) -> dict[str, Any] | None:
    """Most recent sync package record, or None."""
    base = base or base_dir()
    recs = read_chain(base / "sync" / "packages.jsonl")
    return recs[-1] if recs else None


def sync_due(base: Path | None = None) -> tuple[bool, dict[str, Any]]:
    """Is a collective-intelligence sync due? (R7)

    True when the last package is older than cadence_days, or no
    package has ever shipped and there is promoted content waiting.
    """
    base = base or base_dir()
    cfg = get_config(base)
    info: dict[str, Any] = {
        "cadence_days": cfg["cadence_days"],
        "version_vector": version_vector(base),
    }
    last = last_package(base)
    if last is None:
        info["reason"] = "no package shipped yet"
        from .promote import store_count
        info["due"] = store_count(base)["active"] > 0
        return info["due"], info
    from datetime import datetime, timezone

    created = datetime.fromisoformat(last["created_ts"])
    age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
    info["age_days"] = round(age_days, 2)
    info["due"] = age_days >= cfg["cadence_days"]
    return info["due"], info


def build_package(base: Path | None = None) -> dict[str, Any]:
    """Assemble the sync package: manifest + deltas + receipts + vector."""
    base = base or base_dir()
    ts = utcnow().replace(":", "").replace("+", "z")
    pkg_id = "soxi-sync-" + ts
    pkg_dir = base / "sync" / "outbox" / pkg_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    base_vv = {}
    last = last_package(base)
    if last:
        base_vv = last.get("version_vector", {})

    # Deltas: active lessons promoted since the last package.
    conn = sqlite3.connect(str(store_path(base)))
    cur = conn.cursor()
    rows = cur.execute(
        """SELECT lesson_id, kind, subject, persona_id, text, version,
                  correction_of, batch_id, teacher, promoted_ts, promotion_id
           FROM lessons WHERE reverted = 0 ORDER BY promoted_ts"""
    ).fetchall()
    conn.close()
    deltas: list[dict[str, Any]] = []
    for r in rows:
        entry = {
            "lesson_id": r[0], "kind": r[1], "subject": r[2],
            "persona_id": r[3], "text": r[4], "version": r[5],
            "correction_of": r[6], "batch_id": r[7], "teacher": r[8],
            "promoted_ts": r[9], "promotion_id": r[10],
        }
        deltas.append(entry)
    if last:
        after = last["created_ts"]
        deltas = [d for d in deltas if d["promoted_ts"] >= after]

    receipts: list[dict[str, Any]] = []
    for name in ("arrivals", "verdicts", "refinements", "promotions"):
        receipts.extend(read_chain(base / (name + ".jsonl")))

    vv = version_vector(base)
    with open(pkg_dir / "deltas.jsonl", "w", encoding="utf-8") as f:
        for d in deltas:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(pkg_dir / "receipts.jsonl", "w", encoding="utf-8") as f:
        for r in receipts:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(pkg_dir / "version_vector.json", "w", encoding="utf-8") as f:
        json.dump(vv, f, indent=2)

    manifest = {
        "package_id": pkg_id,
        "created_ts": utcnow(),
        "cadence_days": get_config(base)["cadence_days"],
        "base_version_vector": base_vv,
        "version_vector": vv,
        "delta_count": len(deltas),
        "receipt_count": len(receipts),
        "receipt_heads": {
            name: (read_chain(base / (name + ".jsonl")) or [{"hash": None}])[-1].get("hash")
            for name in ("arrivals", "verdicts", "refinements", "promotions")
        },
        "files": ["manifest.json", "deltas.jsonl", "receipts.jsonl",
                  "version_vector.json"],
        "cloud_endpoint": "NEXT BUILD — the cloud ingestor applies this "
                          "package idempotently on version_vector and fans "
                          "out to every connected client.",
    }
    (pkg_dir / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                           encoding="utf-8")

    rec = append_receipt(
        base / "sync" / "packages.jsonl",
        {
            "ts": utcnow(),
            "package_id": pkg_id,
            "created_ts": manifest["created_ts"],
            "version_vector": vv,
            "delta_count": len(deltas),
        },
    )
    return {"package_id": pkg_id, "path": str(pkg_dir),
            "delta_count": len(deltas), "receipt": rec}


def roundtrip_ok(pkg_dir: str | Path) -> tuple[bool, str]:
    """Verify a package: all files present, all JSONL parse, manifest sane."""
    p = Path(pkg_dir)
    for name in ("manifest.json", "deltas.jsonl", "receipts.jsonl",
                 "version_vector.json"):
        if not (p / name).exists():
            return False, "missing " + name
    try:
        manifest = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
        n = 0
        for line in (p / "deltas.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
                n += 1
        for line in (p / "receipts.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
    except ValueError as e:
        return False, "parse error: %s" % e
    if manifest.get("delta_count") != n:
        return False, "manifest delta_count %s != %d actual" % (
            manifest.get("delta_count"), n)
    return True, "ok: %d deltas, %d receipts" % (n, manifest.get("receipt_count"))
