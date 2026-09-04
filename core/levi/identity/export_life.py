"""
Life pack export/import — portable user value (not lock-in).
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json
import zipfile
import shutil

DEFAULT_DIR = Path.home() / ".levi"


def export_life_pack(dest: Optional[Path] = None) -> Path:
    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = Path(dest) if dest else DEFAULT_DIR / f"life_pack_{ts}.zip"

    buf_files: Dict[str, bytes] = {}
    prof = DEFAULT_DIR / "profile.json"
    if prof.exists():
        buf_files["profile.json"] = prof.read_bytes()
    mem = DEFAULT_DIR / "memory"
    if mem.exists():
        for p in mem.rglob("*"):
            if p.is_file():
                buf_files[f"memory/{p.relative_to(mem)}"] = p.read_bytes()
    stories = DEFAULT_DIR / "stories" / "stories.json"
    if stories.exists():
        buf_files["stories/stories.json"] = stories.read_bytes()
    fac = DEFAULT_DIR / "factory" / "projects.json"
    if fac.exists():
        buf_files["factory/projects.json"] = fac.read_bytes()
    auto = DEFAULT_DIR / "automations" / "automations.json"
    if auto.exists():
        buf_files["automations/automations.json"] = auto.read_bytes()
    graph = DEFAULT_DIR / "graph" / "composites.json"
    if graph.exists():
        buf_files["graph/composites.json"] = graph.read_bytes()

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "levi_life_pack_v1",
        "files": list(buf_files.keys()),
        "note": "Portable LEVI value. Free core. Your data stays yours.",
    }
    buf_files["MANIFEST.json"] = json.dumps(manifest, indent=2).encode("utf-8")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in buf_files.items():
            zf.writestr(name, data)
    return dest


def import_life_pack(src: Path, *, merge: bool = True) -> Dict[str, Any]:
    """
    Import a life pack into ~/.levi.
    merge=True keeps existing files not present in the pack;
    merge=False replaces only the namespaces present in the pack.
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"Life pack not found: {src}")

    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {"imported": [], "skipped": [], "format": None}

    with zipfile.ZipFile(src, "r") as zf:
        names = zf.namelist()
        if "MANIFEST.json" in names:
            try:
                man = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
                report["format"] = man.get("format")
            except Exception:
                report["format"] = "unknown"

        mapping = {
            "profile.json": DEFAULT_DIR / "profile.json",
            "stories/stories.json": DEFAULT_DIR / "stories" / "stories.json",
            "factory/projects.json": DEFAULT_DIR / "factory" / "projects.json",
            "automations/automations.json": DEFAULT_DIR / "automations" / "automations.json",
            "graph/composites.json": DEFAULT_DIR / "graph" / "composites.json",
        }

        for archive_name, dest in mapping.items():
            if archive_name not in names:
                report["skipped"].append(archive_name)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and merge:
                # Prefer pack data for continuity restore; still merge=True means we write pack over known namespaces
                pass
            dest.write_bytes(zf.read(archive_name))
            report["imported"].append(archive_name)

        # Memory tree
        mem_members = [n for n in names if n.startswith("memory/") and not n.endswith("/")]
        if mem_members:
            mem_root = DEFAULT_DIR / "memory"
            mem_root.mkdir(parents=True, exist_ok=True)
            for n in mem_members:
                rel = n[len("memory/"):]
                if not rel or ".." in rel:
                    continue
                out = mem_root / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zf.read(n))
                report["imported"].append(n)

    return report
