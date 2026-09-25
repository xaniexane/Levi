"""Stage snapshots for the academy boot camp — the first client of the engine.

Captures the boot camp (syllabus, schedule, lessons, ladder/concepts,
data inventory) at a named stage into an immutable, sealed, hash-chained
snapshot. From any stage you can diff, restore, fork-and-refine,
recreate, and implement — without ever mutating the live academy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.snapshots.stages import StageSnapshot, StageStore

# Small text files are captured by content; anything bigger is captured
# by hash + size so snapshots stay lean.
_CONTENT_EXTS = {".json", ".md", ".txt", ".py"}
_CONTENT_LIMIT = 64 * 1024


def _academy_root(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    return Path(__file__).resolve().parents[1] / "academy"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _inventory(root: Path) -> List[Dict[str, Any]]:
    """Deterministic file inventory: path, size, hash, and small text contents."""
    out: List[Dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        size = p.stat().st_size
        entry: Dict[str, Any] = {
            "path": rel,
            "size": size,
            "sha256": _sha256_file(p),
        }
        if p.suffix.lower() in _CONTENT_EXTS and size <= _CONTENT_LIMIT:
            try:
                entry["content"] = p.read_text(encoding="utf-8")
            except Exception:
                pass
        out.append(entry)
    return out


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_bootcamp_payload(academy_root: Optional[Path] = None) -> Dict[str, Any]:
    """Collect the boot camp's stage-capturable state. Honest: missing parts are None."""
    root = _academy_root(academy_root)
    payload: Dict[str, Any] = {
        "kind": "academy-bootcamp",
        "academy_root": str(root),
    }
    payload["syllabus"] = _read_json(root / "syllabus.json")
    payload["schedule"] = _read_json(root / "schedule.json")
    lessons = root / "lessons"
    payload["lessons"] = _inventory(lessons) if lessons.is_dir() else None
    data = root / "data"
    payload["data"] = _inventory(data) if data.is_dir() else None
    # Module-level stage files the academy owns (hashes keep it honest).
    modules: Dict[str, Any] = {}
    for name in ("ladder.py", "concepts.py", "build_syllabus.py", "session_exercises.py"):
        p = root / name
        if p.is_file():
            modules[name] = {"sha256": _sha256_file(p), "size": p.stat().st_size}
    payload["modules"] = modules
    return payload


def snapshot_bootcamp(
    stage_label: str,
    *,
    note: str = "",
    home: Optional[Path] = None,
    academy_root: Optional[Path] = None,
) -> StageSnapshot:
    """Save the boot camp at a named stage. Returns the immutable snapshot."""
    store = StageStore(home=home)
    payload = collect_bootcamp_payload(academy_root)
    return store.capture_stage(
        name=f"bootcamp:{stage_label}",
        payload=payload,
        stage_label=stage_label,
        note=note,
    )


def diff_bootcamp_stages(a_id: str, b_id: str, home: Optional[Path] = None) -> List[Dict[str, Any]]:
    from levi.snapshots.stages import diff_stages

    return diff_stages(StageStore(home=home), a_id, b_id)


def restore_bootcamp_stage(snapshot_id: str, target_dir: Path, home: Optional[Path] = None) -> Path:
    return StageStore(home=home).restore_stage(snapshot_id, target_dir)


def fork_bootcamp_stage(
    snapshot_id: str,
    stage_label: str,
    *,
    note: str = "",
    home: Optional[Path] = None,
) -> StageSnapshot:
    return StageStore(home=home).fork_stage(
        snapshot_id, f"bootcamp:{stage_label}", stage_label=stage_label, note=note
    )


def list_bootcamp_stages(home: Optional[Path] = None) -> List[StageSnapshot]:
    return [s for s in StageStore(home=home).list_stages() if s.name.startswith("bootcamp:")]
