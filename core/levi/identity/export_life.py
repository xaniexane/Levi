"""
Life pack export/import — portable user value (not lock-in).
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json
import zipfile

DEFAULT_DIR = Path.home() / ".levi"

# Namespaces this importer understands. Anything else in the zip is ignored —
# the importer never writes an archive-controlled path outside this mapping.
_NAMESPACE_FILES = (
    "profile.json",
    "stories/stories.json",
    "factory/projects.json",
    "automations/automations.json",
    "graph/composites.json",
)

_PACK_FORMAT = "levi_life_pack_v1"


def _root(home: Optional[Path]) -> Path:
    return Path(home).expanduser() if home is not None else DEFAULT_DIR


def _deep_merge(base: Any, incoming: Any) -> Any:
    """Merge pack data into existing data; pack wins on scalar conflicts.

    Dicts recurse. Lists of dicts carrying string "id"s merge by id (pack
    item wins per id, order preserved). Other lists union preserving order.
    """
    if isinstance(base, dict) and isinstance(incoming, dict):
        out = dict(base)
        for k, v in incoming.items():
            out[k] = _deep_merge(out[k], v) if k in out else v
        return out
    if isinstance(base, list) and isinstance(incoming, list):
        if (base or incoming) and all(
            isinstance(i, dict) and isinstance(i.get("id"), str)
            for i in base + incoming
        ):
            merged = {i["id"]: i for i in base}
            for i in incoming:
                merged[i["id"]] = (
                    _deep_merge(merged[i["id"]], i) if i["id"] in merged else i
                )
            seen: set = set()
            out_list = []
            for i in base + incoming:
                if i["id"] not in seen:
                    seen.add(i["id"])
                    out_list.append(merged[i["id"]])
            return out_list
        out_list = list(base)
        for i in incoming:
            if i not in out_list:
                out_list.append(i)
        return out_list
    return incoming


def _write_namespace_file(dest: Path, data: bytes, *, merge: bool) -> str:
    """Write one namespace file. Returns 'wrote' | 'merged' | 'kept'.

    merge=True deep-merges pack JSON into an existing JSON file (pack wins
    on conflicts) instead of overwriting it; non-JSON content is replaced.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if merge and dest.exists():
        try:
            existing = json.loads(dest.read_bytes().decode("utf-8"))
            incoming = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            existing = incoming = None
        if isinstance(existing, dict) and isinstance(incoming, dict):
            merged = _deep_merge(existing, incoming)
            if merged != existing:
                dest.write_bytes(
                    json.dumps(merged, indent=2, ensure_ascii=False).encode("utf-8")
                )
                return "merged"
            return "kept"
    dest.write_bytes(data)
    return "wrote"


def _safe_member_path(root: Path, rel: str) -> Optional[Path]:
    """Resolve a zip member path, or None when it escapes ``root`` (zip-slip)."""
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return None
    out = root / rel
    try:
        out.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return out


def export_life_pack(dest: Optional[Path] = None, home: Optional[Path] = None) -> Path:
    home_dir = _root(home)
    home_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = Path(dest).expanduser() if dest else home_dir / f"life_pack_{ts}.zip"
    if dest.exists() and not dest.is_file():
        raise ValueError(f"export destination is not a file: {dest}")

    buf_files: Dict[str, bytes] = {}
    prof = home_dir / "profile.json"
    if prof.exists():
        buf_files["profile.json"] = prof.read_bytes()
    mem = home_dir / "memory"
    if mem.exists():
        for p in mem.rglob("*"):
            if p.is_file():
                buf_files[f"memory/{p.relative_to(mem)}"] = p.read_bytes()
    stories = home_dir / "stories" / "stories.json"
    if stories.exists():
        buf_files["stories/stories.json"] = stories.read_bytes()
    fac = home_dir / "factory" / "projects.json"
    if fac.exists():
        buf_files["factory/projects.json"] = fac.read_bytes()
    auto = home_dir / "automations" / "automations.json"
    if auto.exists():
        buf_files["automations/automations.json"] = auto.read_bytes()
    graph = home_dir / "graph" / "composites.json"
    if graph.exists():
        buf_files["graph/composites.json"] = graph.read_bytes()

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": _PACK_FORMAT,
        "files": list(buf_files.keys()),
        "note": "Portable LEVI value. Free core. Your data stays yours.",
    }
    buf_files["MANIFEST.json"] = json.dumps(manifest, indent=2).encode("utf-8")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in buf_files.items():
            zf.writestr(name, data)
    return dest


def import_life_pack(
    src: Path, *, merge: bool = True, home: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Import a life pack into the LEVI home (``~/.levi`` by default).

    merge=True (default) keeps existing local state: pack JSON is
    deep-merged into existing namespace files (pack wins on conflicts)
    and existing memory files are left untouched; only files absent
    locally are added. merge=False replaces every namespace present in
    the pack with the pack's bytes. Files outside the known namespaces
    are never written.

    Raises:
        FileNotFoundError: ``src`` does not exist.
        ValueError: ``src`` is not a valid life-pack zip.
    """
    src = Path(src).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"Life pack not found: {src}")
    home_dir = _root(home)
    home_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "imported": [],
        "skipped": [],
        "kept_existing": [],
        "format": None,
    }

    try:
        zf = zipfile.ZipFile(src, "r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid life-pack zip: {src} ({exc})") from exc
    with zf:
        names = zf.namelist()
        if "MANIFEST.json" in names:
            try:
                man = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
                report["format"] = man.get("format")
            except (ValueError, UnicodeDecodeError, KeyError):
                report["format"] = "unknown"
        if report["format"] not in (None, "unknown", _PACK_FORMAT):
            report["skipped"].append(f"unexpected pack format: {report['format']!r}")

        for archive_name in _NAMESPACE_FILES:
            if archive_name not in names:
                report["skipped"].append(archive_name)
                continue
            dest = home_dir / archive_name
            try:
                data = zf.read(archive_name)
            except KeyError:
                report["skipped"].append(archive_name)
                continue
            outcome = _write_namespace_file(dest, data, merge=merge)
            if outcome == "kept":
                report["kept_existing"].append(archive_name)
            else:
                report["imported"].append(archive_name)

        # Memory tree
        mem_members = [
            n for n in names if n.startswith("memory/") and not n.endswith("/")
        ]
        if mem_members:
            mem_root = home_dir / "memory"
            mem_root.mkdir(parents=True, exist_ok=True)
            for n in mem_members:
                rel = n[len("memory/") :]
                out = _safe_member_path(mem_root, rel)
                if out is None:
                    report["skipped"].append(n)  # zip-slip attempt: never written
                    continue
                if merge and out.exists():
                    report["kept_existing"].append(n)
                    continue
                try:
                    data = zf.read(n)
                except KeyError:
                    report["skipped"].append(n)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                report["imported"].append(n)

    return report
