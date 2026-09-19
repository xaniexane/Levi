"""Dual-reality file mechanics: create, read, verify, seal."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SIDE_A_HEAD = "## SIDE A — PHYSICAL"
SIDE_B_HEAD = "## SIDE B — CANON"
MARKER = "<!-- dual-reality:1 -->"


@dataclass
class DualFile:
    path: Path
    title: str
    physical: str
    canon: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "path": str(self.path),
            "title": self.title,
            "physical": self.physical,
            "canon": self.canon,
        }


def _render(title: str, physical: str, canon: str) -> str:
    return (
        f"{MARKER}\n# {title}\n\n"
        f"{SIDE_A_HEAD}\n\n{physical.strip()}\n\n"
        f"{SIDE_B_HEAD}\n\n{canon.strip()}\n"
    )


def create(path: Path, title: str, physical: str, canon: str) -> DualFile:
    """Write a new dual-reality file. Both sides required — no half files."""
    if not physical.strip():
        raise ValueError("dual file requires SIDE A (physical)")
    if not canon.strip():
        raise ValueError("dual file requires SIDE B (canon)")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_render(title, physical, canon), encoding="utf-8")
    return DualFile(path=p, title=title, physical=physical.strip(), canon=canon.strip())


def read(path: Path) -> DualFile:
    """Parse a dual-reality file; raises ValueError when malformed."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if MARKER not in text:
        raise ValueError(f"not a dual-reality file: {p}")
    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else p.stem
    a_m = re.search(
        rf"{re.escape(SIDE_A_HEAD)}\n\n(.*?)\n\n{re.escape(SIDE_B_HEAD)}",
        text,
        re.DOTALL,
    )
    b_m = re.search(rf"{re.escape(SIDE_B_HEAD)}\n\n(.*)$", text, re.DOTALL)
    if not a_m or not b_m:
        raise ValueError(f"dual-reality file missing a side: {p}")
    return DualFile(
        path=p, title=title, physical=a_m.group(1).strip(), canon=b_m.group(1).strip()
    )


def verify(path: Path) -> Dict[str, object]:
    """Check the two sides are present, non-empty, and cross-referenced.

    Cross-reference rule: the canon side must name what the physical side
    does (shared vocabulary), and the physical side must serve the canon's
    stated purpose. Checked cheaply via shared significant words.
    """
    issues: List[str] = []
    try:
        df = read(path)
    except (ValueError, OSError) as e:
        return {"path": str(path), "in_sync": False, "issues": [str(e)]}
    if not df.physical:
        issues.append("SIDE A (physical) is empty")
    if not df.canon:
        issues.append("SIDE B (canon) is empty")

    def _sigwords(t: str) -> set:
        words = re.findall(r"[a-z]{4,}", t.lower())
        stop = {
            "what",
            "this",
            "that",
            "with",
            "from",
            "into",
            "side",
            "canon",
            "physical",
            "reality",
            "dual",
            "file",
        }
        return {w for w in words if w not in stop}

    shared = _sigwords(df.physical) & _sigwords(df.canon)
    if not shared and df.physical and df.canon:
        issues.append(
            "sides share no vocabulary — canon does not describe the physical"
        )
    return {
        "path": str(path),
        "in_sync": not issues,
        "issues": issues,
        "shared_terms": sorted(shared)[:10],
    }


def _seal_path() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "dual" / "seals.jsonl"


def _digest(df: DualFile) -> str:
    raw = f"{df.title}\n---A---\n{df.physical}\n---B---\n{df.canon}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seal(path: Path) -> Dict[str, str]:
    """Identity-lock a synced dual file. Sealing an out-of-sync file is refused."""
    report = verify(path)
    if not report["in_sync"]:
        raise ValueError(f"refusing to seal out-of-sync file: {report['issues']}")
    df = read(Path(path))
    sp = _seal_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "path": str(df.path),
        "digest": _digest(df),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with sp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    try:
        os.chmod(sp, 0o600)
    except OSError:
        pass
    return entry


def verify_seal(path: Path) -> Dict[str, object]:
    """True when the file still matches its latest seal (no drift)."""
    df = read(Path(path))
    sp = _seal_path()
    if not sp.exists():
        return {"path": str(path), "sealed": False, "reason": "no seals on record"}
    latest: Optional[Dict] = None
    for line in sp.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("path") == str(df.path):
            latest = row
    if latest is None:
        return {"path": str(path), "sealed": False, "reason": "never sealed"}
    drifted = latest["digest"] != _digest(df)
    return {
        "path": str(path),
        "sealed": not drifted,
        "drifted": drifted,
        "sealed_at": latest.get("ts"),
    }
