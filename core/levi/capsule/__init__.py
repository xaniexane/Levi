"""LEVI TimeCapsule — portable state seeds.

Create a compressed, owner-only seed of LEVI state (dream journal, memory
snapshots, config) and plant it elsewhere — phone, new machine, fresh
install. Concept adapted from the Levi 30.x lineage; original implementation.

Seeds are gzip-compressed JSON with a manifest. Planting never overwrites
blindly: it merges journal lines (dedup by content hash) and reports what
landed.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

SEED_SUFFIX = ".lseed"
MANIFEST_KIND = "levi-timecapsule/1"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def default_seed_dir() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    d = base / "capsule"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_seed(
    sources: Dict[str, Path] | None = None, dest_dir: Path | None = None
) -> Path:
    """Bundle sources ({name: path}) into a .lseed file. Returns the path."""
    dest_dir = dest_dir or default_seed_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    if sources is None:
        sources = {
            "dream_journal": base / "dream" / "journal.jsonl",
            "growth_journal": base / "growth" / "journal.jsonl",
        }
    payload: Dict[str, Any] = {
        "manifest": {"kind": MANIFEST_KIND, "created": _utcnow()},
        "parts": {},
    }
    for name, path in sources.items():
        p = Path(path)
        if p.exists() and p.is_file():
            try:
                payload["parts"][name] = p.read_text(encoding="utf-8")
            except OSError:
                continue
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = dest_dir / f"levi_seed_{stamp}{SEED_SUFFIX}"
    out.write_bytes(gzip.compress(raw))
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    return out


def inspect_seed(seed_path: Path) -> Dict[str, Any]:
    """Read a seed's manifest without planting."""
    p = Path(seed_path)
    payload = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    manifest = payload.get("manifest", {})
    parts = payload.get("parts", {})
    return {
        "kind": manifest.get("kind"),
        "created": manifest.get("created"),
        "parts": {k: len(v) for k, v in parts.items()},
    }


def plant_seed(seed_path: Path, dest_base: Path | None = None) -> Dict[str, Any]:
    """Merge a seed into local state. Journal lines dedup by content hash."""
    p = Path(seed_path)
    if not p.exists():
        return {"ok": False, "error": "seed file not found"}
    try:
        payload = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"unreadable seed: {e}"}
    if payload.get("manifest", {}).get("kind") != MANIFEST_KIND:
        return {"ok": False, "error": "not a LEVI timecapsule seed"}
    base = dest_base or Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    report: Dict[str, Any] = {"ok": True, "merged": {}, "skipped": []}
    for name, content in payload.get("parts", {}).items():
        if name.endswith("_journal"):
            # journal-style merge: append only lines not already present
            target = (
                base / "dream" / "journal.jsonl"
                if name == "dream_journal"
                else base / "growth" / "journal.jsonl"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = set()
            if target.exists():
                for line in target.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        existing.add(_sha(line))
            added = 0
            with target.open("a", encoding="utf-8") as fh:
                for line in content.splitlines():
                    if line.strip() and _sha(line) not in existing:
                        fh.write(line + "\n")
                        existing.add(_sha(line))
                        added += 1
            report["merged"][name] = added
        else:
            report["skipped"].append(name)
    return report
