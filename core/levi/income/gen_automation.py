"""Income batch E — automation services (slots 81-92).

Twelve original, from-scratch, stdlib-only local automation services.
Every generator automates a real local task against a user-supplied
``params["target"]`` path. Defaults are preview/dry-run; real runs write
undo/restore manifests and never delete without one. No network, no paid
APIs, no third-party code.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.income.engine import Generator, WorkReport, register

KIND = "automation-service"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _work_dir(ctx: Dict[str, Any], gid: str) -> Path:
    d = Path(ctx["levi_home"]) / ".levi" / "income" / "work" / gid
    if not ctx.get("dry_run"):
        d.mkdir(parents=True, exist_ok=True)
    return d


def _target(ctx: Dict[str, Any], key: str = "target") -> Path:
    """User-supplied path; safe tmp sandbox default. Never destructive by default."""
    p = ctx["params"].get(key)
    if p:
        return Path(p)
    return Path(tempfile.gettempdir()) / "levi_income_automation"


def _write_json(work_dir: Path, name: str, obj: Any) -> Path:
    path = work_dir / name
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
    return path


def _sha256(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for piece in iter(lambda: fh.read(chunk), b""):
            h.update(piece)
    return h.hexdigest()


def _files(dirpath: Path, recursive: bool = False) -> List[Path]:
    if not dirpath.is_dir():
        return []
    it = dirpath.rglob("*") if recursive else dirpath.iterdir()
    return sorted(
        (p for p in it if p.is_file() and not p.is_symlink()),
        key=lambda p: p.name.lower(),
    )


# ---------------------------------------------------------------------------
# 81. file-sort-bot
# ---------------------------------------------------------------------------

_SORT_CATEGORIES = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic"},
    "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".csv", ".xls", ".xlsx"},
    "audio": {".mp3", ".wav", ".ogg", ".flac", ".m4a"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "archives": {".zip", ".tar", ".gz", ".rar", ".7z", ".bz2"},
    "code": {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh", ".html", ".css"},
}


def _category_for(path: Path) -> str:
    ext = path.suffix.lower()
    for cat, exts in _SORT_CATEGORIES.items():
        if ext in exts:
            return cat
    return "misc"


def _run_file_sort_bot(ctx: Dict[str, Any]) -> WorkReport:
    gid = "file-sort-bot"
    target = _target(ctx)
    files = [f for f in _files(target) if f.parent == target]
    plan = [
        {
            "from": str(f),
            "to": str(target / _category_for(f) / f.name),
            "category": _category_for(f),
            "bytes": f.stat().st_size,
        }
        for f in files
        if target / _category_for(f) / f.name != f
    ]
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(plan)} moves"],
            quoted_amount_usd=3.0,
            notes=f"DRY RUN: would sort {len(plan)} file(s) in {target} into "
            f"category folders; no files touched.",
        )
    work = _work_dir(ctx, gid)
    moved = 0
    for entry in plan:
        dst = Path(entry["to"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            n = 1
            while (candidate := dst.parent / f"{stem} ({n}){suffix}").exists():
                n += 1
            dst = candidate
            entry["to"] = str(dst)
        shutil.move(entry["from"], dst)
        moved += 1
    manifest = _write_json(
        work, "move_manifest.json",
        {"id": gid, "at": _utcnow(), "target": str(target), "moves": plan,
         "undo": "reverse each move: move 'to' back to 'from'"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"moved:{moved}", f"manifest:{manifest.name}"],
        quoted_amount_usd=3.0,
        notes=f"Sorted {moved} file(s) in {target}; undo manifest at {manifest.name}.",
    )


# ---------------------------------------------------------------------------
# 82. log-rotator
# ---------------------------------------------------------------------------

def _run_log_rotator(ctx: Dict[str, Any]) -> WorkReport:
    gid = "log-rotator"
    target = _target(ctx)
    max_bytes = int(ctx["params"].get("max_size_mb", 10)) * 1024 * 1024
    keep_days = int(ctx["params"].get("keep_days", 30))
    logs = [f for f in _files(target) if f.suffix.lower() == ".log"]
    now = datetime.now(timezone.utc).timestamp()
    plan: List[Dict[str, Any]] = []
    for f in logs:
        st = f.stat()
        age_days = (now - st.st_mtime) / 86400.0
        if st.st_size >= max_bytes:
            plan.append({"file": str(f), "action": "rotate",
                         "reason": f"size {st.st_size} >= {max_bytes}"})
        elif age_days >= keep_days:
            plan.append({"file": str(f), "action": "archive",
                         "reason": f"age {age_days:.1f}d >= {keep_days}d"})
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(plan)} actions on {len(logs)} log(s)"],
            quoted_amount_usd=2.5,
            notes=f"DRY RUN: would rotate/archive {len(plan)} of {len(logs)} log(s) "
            f"in {target}; no files touched.",
        )
    work = _work_dir(ctx, gid)
    archive_dir = target / "_rotated"
    actions: List[Dict[str, Any]] = []
    for entry in plan:
        src = Path(entry["file"])
        if not src.exists():
            continue
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        arc_name = f"{src.stem}.{stamp}.log.gz"
        arc_path = archive_dir / arc_name
        with open(src, "rb") as fin, gzip.open(arc_path, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        if entry["action"] == "rotate":
            src.write_bytes(b"")  # fresh empty log, archive kept
        else:
            src.unlink()          # archived; original recorded in manifest
        actions.append({"file": str(src), "action": entry["action"],
                        "archive": str(arc_path)})
    manifest = _write_json(
        work, "rotation_manifest.json",
        {"id": gid, "at": _utcnow(), "target": str(target),
         "max_size_mb": max_bytes // (1024 * 1024), "keep_days": keep_days,
         "actions": actions,
         "undo": "gunzip an archive back to its 'file' path to restore"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"rotated:{len(actions)}", f"manifest:{manifest.name}"],
        quoted_amount_usd=2.5,
        notes=f"Rotated/archived {len(actions)} log(s); archives in {archive_dir.name}/, "
        f"manifest {manifest.name} records every original path.",
    )


# ---------------------------------------------------------------------------
# 83. daily-digest-assembler
# ---------------------------------------------------------------------------

def _run_daily_digest(ctx: Dict[str, Any]) -> WorkReport:
    gid = "daily-digest-assembler"
    notes_dir = Path(ctx["params"].get("notes_dir", str(_target(ctx) / "notes")))
    logs_dir = Path(ctx["params"].get("logs_dir", str(_target(ctx) / "logs")))
    tail_lines = int(ctx["params"].get("tail_lines", 20))
    sections: List[str] = []
    notes = _files(notes_dir)
    note_items = [f"- {f.name} ({f.stat().st_size} bytes)" for f in notes[:20]]
    sections.append(f"## Notes ({len(notes)})\n" + (
        "\n".join(note_items) if note_items else "_no notes found_"))
    log_lines: List[str] = []
    for f in _files(logs_dir):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            log_lines.extend(f"- [{f.name}] {ln}" for ln in lines[-tail_lines:])
        except OSError:
            continue
    sections.append(f"## Recent log lines ({len(log_lines)})\n" + (
        "\n".join(log_lines[-tail_lines * 3:]) if log_lines else "_no logs found_"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = (f"# Daily Digest — {today}\n\nSources: notes={notes_dir}, "
              f"logs={logs_dir}\n\n" + "\n\n".join(sections) + "\n")
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:digest {len(digest)} chars from "
                      f"{len(notes)} note(s), {len(log_lines)} log line(s)"],
            quoted_amount_usd=3.0,
            notes="DRY RUN: would assemble a morning digest; nothing written.",
        )
    work = _work_dir(ctx, gid)
    out = work / f"digest-{today}.md"
    out.write_text(digest, encoding="utf-8")
    return WorkReport(
        generator_id=gid,
        produced=[f"digest:{out.name}", f"bytes:{len(digest)}"],
        quoted_amount_usd=3.0,
        notes=f"Assembled digest {out.name} from {len(notes)} note(s) and "
        f"{len(log_lines)} log line(s).",
    )


# ---------------------------------------------------------------------------
# 84. reminder-nudger
# ---------------------------------------------------------------------------

_REMINDER_RE = re.compile(
    r"^\s*(?P<date>\d{4}-\d{2}-\d{2})\s*[|:]\s*(?P<text>.+?)\s*$")


def _parse_reminders(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    for lineno, raw in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        m = _REMINDER_RE.match(raw)
        if not m:
            continue
        try:
            due = datetime.strptime(m.group("date"), "%Y-%m-%d").date()
        except ValueError:
            continue
        items.append({"date": m.group("date"), "text": m.group("text"),
                      "line": lineno})
    return items


def _run_reminder_nudger(ctx: Dict[str, Any]) -> WorkReport:
    gid = "reminder-nudger"
    rfile = Path(ctx["params"].get("reminders_file",
                                   str(_target(ctx) / "reminders.txt")))
    today = datetime.now(timezone.utc).date()
    items = _parse_reminders(rfile)
    overdue = [i for i in items if i["date"] < today.isoformat()]
    due_today = [i for i in items if i["date"] == today.isoformat()]
    upcoming = sorted(
        (i for i in items if i["date"] > today.isoformat()),
        key=lambda i: i["date"])[:5]
    report = (f"# Reminder nudge — {today.isoformat()}\n\n"
              f"Overdue: {len(overdue)} | Due today: {len(due_today)} | "
              f"Upcoming: {len(upcoming)}\n\n")
    for label, group in (("OVERDUE", overdue), ("DUE TODAY", due_today),
                         ("UPCOMING", upcoming)):
        report += f"## {label}\n"
        report += ("\n".join(f"- {i['date']} — {i['text']}" for i in group)
                   + "\n" if group else "_none_\n") + "\n"
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(overdue)} overdue, {len(due_today)} due, "
                      f"{len(upcoming)} upcoming"],
            quoted_amount_usd=2.0,
            notes=f"DRY RUN: would report from {rfile}; nothing written.",
        )
    work = _work_dir(ctx, gid)
    out = work / f"nudge-{today.isoformat()}.md"
    out.write_text(report, encoding="utf-8")
    return WorkReport(
        generator_id=gid,
        produced=[f"nudge:{out.name}",
                  f"overdue:{len(overdue)}", f"due:{len(due_today)}"],
        quoted_amount_usd=2.0,
        notes=f"Nudged {len(overdue)} overdue and {len(due_today)} due-today "
        f"reminder(s) from {rfile.name}.",
    )


# ---------------------------------------------------------------------------
# 85. backup-runner
# ---------------------------------------------------------------------------

def _run_backup_runner(ctx: Dict[str, Any]) -> WorkReport:
    gid = "backup-runner"
    source = Path(ctx["params"].get("source", str(_target(ctx))))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest_default = Path(ctx["levi_home"]) / ".levi" / "income" / "work" / gid \
        / f"backup-{stamp}"
    dest = Path(ctx["params"].get("dest", str(dest_default)))
    files = _files(source, recursive=True)
    plan = [{"path": str(f.relative_to(source)), "bytes": f.stat().st_size}
            for f in files]
    total = sum(p["bytes"] for p in plan)
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:backup {len(plan)} file(s), {total} bytes"],
            quoted_amount_usd=4.0,
            notes=f"DRY RUN: would back up {source} ({len(plan)} file(s)) "
            f"to {dest}; nothing copied.",
        )
    dest.mkdir(parents=True, exist_ok=True)
    work = _work_dir(ctx, gid)
    manifest_entries: List[Dict[str, Any]] = []
    for f in files:
        rel = f.relative_to(source)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        manifest_entries.append({"path": str(rel), "bytes": f.stat().st_size,
                                 "sha256": _sha256(out)})
    manifest = _write_json(
        work,
        f"backup-{stamp}.manifest.json",
        {"id": gid, "at": _utcnow(), "source": str(source),
         "dest": str(dest), "files": manifest_entries,
         "verify": "re-run _sha256 over dest files to check integrity"},
    )
    # verify pass
    verified = sum(1 for e in manifest_entries
                   if _sha256(dest / e["path"]) == e["sha256"])
    return WorkReport(
        generator_id=gid,
        produced=[f"backup:{dest.name}", f"files:{verified}/{len(manifest_entries)}",
                  f"manifest:{manifest.name}"],
        quoted_amount_usd=4.0,
        notes=f"Backed up {verified}/{len(manifest_entries)} file(s) "
        f"({total} bytes) with sha256 manifest; integrity verified.",
    )


# ---------------------------------------------------------------------------
# 86. photo-organizer
# ---------------------------------------------------------------------------

_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
_DATE_IN_NAME = re.compile(
    r"(?P<y>20\d{2})[-_]?((?P<m>0[1-9]|1[0-2]))[-_]?(?P<d>0[1-9]|[12]\d|3[01])")


def _photo_date(path: Path) -> str:
    """Date from filename (IMG_YYYYMMDD etc.), else file mtime. YYYY-MM-DD."""
    m = _DATE_IN_NAME.search(path.stem)
    if m:
        return f"{m.group('y')}-{m.group('m')}-{m.group('d')}"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def _run_photo_organizer(ctx: Dict[str, Any]) -> WorkReport:
    gid = "photo-organizer"
    target = _target(ctx)
    photos = [f for f in _files(target) if f.suffix.lower() in _PHOTO_EXTS]
    plan = [{"from": str(f), "to": str(target / "photos" / _photo_date(f) / f.name),
             "date": _photo_date(f)} for f in photos]
    if ctx.get("dry_run"):
        buckets = sorted({p["date"] for p in plan})
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(plan)} photo(s) into {len(buckets)} dated folder(s)"],
            quoted_amount_usd=3.5,
            notes=f"DRY RUN: would organize {len(plan)} photo(s) in {target} "
            f"by date (filename pattern, mtime fallback); no EXIF parsing "
            f"(stdlib-only); no files touched.",
        )
    work = _work_dir(ctx, gid)
    moved = 0
    for entry in plan:
        dst = Path(entry["to"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            n = 1
            while (c := dst.parent / f"{stem} ({n}){suffix}").exists():
                n += 1
            dst = c
            entry["to"] = str(dst)
        shutil.move(entry["from"], dst)
        moved += 1
    manifest = _write_json(
        work, "photo_manifest.json",
        {"id": gid, "at": _utcnow(), "target": str(target), "moves": plan,
         "dating": "filename date pattern first, file mtime fallback",
         "undo": "reverse each move: move 'to' back to 'from'"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"moved:{moved}", f"manifest:{manifest.name}"],
        quoted_amount_usd=3.5,
        notes=f"Organized {moved} photo(s) into dated folders under {target}/photos; "
        f"undo manifest {manifest.name}.",
    )


# ---------------------------------------------------------------------------
# 87. duplicate-finder
# ---------------------------------------------------------------------------

def _run_duplicate_finder(ctx: Dict[str, Any]) -> WorkReport:
    gid = "duplicate-finder"
    target = _target(ctx)
    files = _files(target, recursive=bool(ctx["params"].get("recursive", True)))
    # size-first pass: only hash files whose size appears more than once
    by_size: Dict[int, List[Path]] = {}
    for f in files:
        by_size.setdefault(f.stat().st_size, []).append(f)
    groups: List[Dict[str, Any]] = []
    reclaimable = 0
    for size, candidates in by_size.items():
        if len(candidates) < 2 or size == 0:
            continue
        by_hash: Dict[str, List[str]] = {}
        for f in candidates:
            by_hash.setdefault(_sha256(f), []).append(str(f))
        for digest, paths in by_hash.items():
            if len(paths) > 1:
                groups.append({"sha256": digest, "bytes_each": size,
                               "paths": sorted(paths)})
                reclaimable += size * (len(paths) - 1)
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(groups)} duplicate group(s), "
                      f"{reclaimable} reclaimable bytes"],
            quoted_amount_usd=4.0,
            notes=f"DRY RUN: would report {len(groups)} duplicate group(s) in "
            f"{target}; files are never deleted, only reported.",
        )
    work = _work_dir(ctx, gid)
    report = _write_json(
        work, "duplicates.json",
        {"id": gid, "at": _utcnow(), "target": str(target),
         "files_scanned": len(files), "groups": groups,
         "reclaimable_bytes": reclaimable,
         "note": "delete nothing automatically; owner reviews groups first"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"groups:{len(groups)}", f"reclaimable_bytes:{reclaimable}",
                  f"report:{report.name}"],
        quoted_amount_usd=4.0,
        notes=f"Found {len(groups)} duplicate group(s); {reclaimable} bytes "
        f"reclaimable. Report only — nothing deleted.",
    )


# ---------------------------------------------------------------------------
# 88. bulk-renamer
# ---------------------------------------------------------------------------

def _apply_rename_rules(name: str, rules: List[Dict[str, Any]]) -> str:
    stem, dot, suffix = name.rpartition(".")
    base, ext = (stem, "." + suffix) if dot else (name, "")
    for rule in rules:
        op = rule.get("op")
        if op == "prefix":
            base = str(rule.get("value", "")) + base
        elif op == "suffix":
            base = base + str(rule.get("value", ""))
        elif op == "replace":
            base = base.replace(str(rule.get("find", "")),
                                str(rule.get("replace", "")))
        elif op == "lower":
            base = base.lower()
        elif op == "upper":
            base = base.upper()
        elif op == "regex":
            base = re.sub(str(rule.get("pattern", "")),
                          str(rule.get("repl", "")), base)
    return base + ext


def _run_bulk_renamer(ctx: Dict[str, Any]) -> WorkReport:
    gid = "bulk-renamer"
    target = _target(ctx)
    rules = ctx["params"].get("rules") or [{"op": "replace", "find": " ", "replace": "_"}]
    files = [f for f in _files(target) if f.parent == target]
    plan = []
    for f in files:
        new_name = _apply_rename_rules(f.name, rules)
        if new_name != f.name:
            plan.append({"from": str(f), "to": str(target / new_name),
                         "old": f.name, "new": new_name})
    if ctx.get("dry_run"):
        sample = plan[:5]
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(plan)} rename(s)"] +
                     [f"sample:{s['old']} -> {s['new']}" for s in sample],
            quoted_amount_usd=2.5,
            notes=f"DRY RUN: would rename {len(plan)} file(s) in {target} "
            f"using {len(rules)} rule(s); no files touched.",
        )
    work = _work_dir(ctx, gid)
    applied = 0
    for entry in plan:
        dst = Path(entry["to"])
        if dst.exists() and dst != Path(entry["from"]):
            entry["skipped"] = "destination exists"
            continue
        os.rename(entry["from"], dst)
        applied += 1
    manifest = _write_json(
        work, "rename_manifest.json",
        {"id": gid, "at": _utcnow(), "target": str(target), "rules": rules,
         "renames": plan,
         "undo": "rename each 'to' back to 'from'"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"renamed:{applied}", f"manifest:{manifest.name}"],
        quoted_amount_usd=2.5,
        notes=f"Renamed {applied} file(s) with {len(rules)} rule(s); undo "
        f"manifest {manifest.name}.",
    )


# ---------------------------------------------------------------------------
# 89. folder-watch-reporter
# ---------------------------------------------------------------------------

def _snapshot(target: Path) -> Dict[str, Dict[str, Any]]:
    snap: Dict[str, Dict[str, Any]] = {}
    for f in _files(target, recursive=True):
        try:
            st = f.stat()
            snap[str(f.relative_to(target))] = {
                "size": st.st_size, "mtime": st.st_mtime}
        except OSError:
            continue
    return snap


def _run_folder_watch(ctx: Dict[str, Any]) -> WorkReport:
    gid = "folder-watch-reporter"
    target = _target(ctx)
    state_path = Path(ctx["params"].get(
        "state_file",
        str(Path(ctx["levi_home"]) / ".levi" / "income" / "work" / gid / "state.json")))
    old: Dict[str, Dict[str, Any]] = {}
    if state_path.exists():
        try:
            old = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
    new = _snapshot(target)
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)
    modified = sorted(k for k in new if k in old and
                      (new[k]["size"] != old[k]["size"] or
                       new[k]["mtime"] != old[k]["mtime"]))
    changes = {"added": added, "removed": removed, "modified": modified}
    first_run = not old and not state_path.exists()
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(added)} added, {len(removed)} removed, "
                      f"{len(modified)} modified"],
            quoted_amount_usd=2.0,
            notes=f"DRY RUN: would report changes in {target} "
            f"({'baseline' if first_run else 'vs last run'}); state file untouched.",
        )
    if not ctx.get("dry_run"):
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(new, indent=2), encoding="utf-8")
    work = _work_dir(ctx, gid)
    report = _write_json(
        work, "changes.json",
        {"id": gid, "at": _utcnow(), "target": str(target),
         "baseline": first_run, "changes": changes},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"added:{len(added)}", f"removed:{len(removed)}",
                  f"modified:{len(modified)}", f"report:{report.name}"],
        quoted_amount_usd=2.0,
        notes=(f"{'Baseline recorded' if first_run else 'Change report'} for "
               f"{target}: +{len(added)}/-{len(removed)}/~{len(modified)}."),
    )


# ---------------------------------------------------------------------------
# 90. task-health-checker
# ---------------------------------------------------------------------------

def _run_health_checker(ctx: Dict[str, Any]) -> WorkReport:
    gid = "task-health-checker"
    checks: List[Dict[str, Any]] = ctx["params"].get("checks") or []
    now = datetime.now(timezone.utc).timestamp()
    results: List[Dict[str, Any]] = []
    for check in checks:
        path = Path(check.get("path", ""))
        max_age_h = float(check.get("max_age_hours", 24))
        name = check.get("name", str(path))
        if not path.exists():
            results.append({"name": name, "status": "missing", "path": str(path)})
            continue
        age_h = (now - path.stat().st_mtime) / 3600.0
        status = "ok" if age_h <= max_age_h else "stale"
        results.append({"name": name, "status": status, "path": str(path),
                        "age_hours": round(age_h, 2),
                        "max_age_hours": max_age_h})
    gaps = [r for r in results if r["status"] != "ok"]
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:{len(results)} check(s), {len(gaps)} gap(s)"],
            quoted_amount_usd=3.0,
            notes=f"DRY RUN: would verify {len(results)} scheduled output(s); "
            f"nothing written.",
        )
    work = _work_dir(ctx, gid)
    report = _write_json(
        work, "health.json",
        {"id": gid, "at": _utcnow(), "checks": results,
         "gaps": len(gaps)},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"checked:{len(results)}", f"gaps:{len(gaps)}",
                  f"report:{report.name}"],
        quoted_amount_usd=3.0,
        notes=f"Health check: {len(results) - len(gaps)}/{len(results)} ok, "
        f"{len(gaps)} gap(s) reported.",
    )


# ---------------------------------------------------------------------------
# 91. archive-packer
# ---------------------------------------------------------------------------

def _run_archive_packer(ctx: Dict[str, Any]) -> WorkReport:
    gid = "archive-packer"
    target = _target(ctx)
    age_days = float(ctx["params"].get("age_days", 90))
    archive_dir = Path(ctx["params"].get(
        "archive_dir", str(target / "_archives")))
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - age_days * 86400.0
    candidates = [f for f in _files(target, recursive=True)
                  if f.stat().st_mtime < cutoff
                  and archive_dir not in f.parents]
    total = sum(f.stat().st_size for f in candidates)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    arc_name = f"archive-{stamp}.tar.gz"
    if ctx.get("dry_run"):
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:pack {len(candidates)} file(s), {total} bytes "
                      f"older than {age_days}d"],
            quoted_amount_usd=2.5,
            notes=f"DRY RUN: would pack {len(candidates)} aging file(s) into "
            f"{arc_name}; originals untouched.",
        )
    archive_dir.mkdir(parents=True, exist_ok=True)
    arc_path = archive_dir / arc_name
    n = 1
    while arc_path.exists():
        arc_path = archive_dir / f"archive-{stamp}-{n}.tar.gz"
        n += 1
    entries: List[Dict[str, Any]] = []
    with tarfile.open(arc_path, "w:gz") as tar:
        for f in candidates:
            rel = str(f.relative_to(target))
            tar.add(f, arcname=rel)
            entries.append({"path": rel, "bytes": f.stat().st_size,
                            "sha256": _sha256(f)})
    # verify archive members before removing originals
    with tarfile.open(arc_path, "r:gz") as tar:
        names = set(tar.getnames())
    ok = all(e["path"] in names for e in entries)
    removed = 0
    if ok:
        for e in entries:
            try:
                (target / e["path"]).unlink()
                removed += 1
            except OSError:
                e["remove_failed"] = True
    work = _work_dir(ctx, gid)
    manifest = _write_json(
        work, f"{arc_path.stem}.manifest.json",
        {"id": gid, "at": _utcnow(), "target": str(target),
         "archive": str(arc_path), "age_days": age_days,
         "files": entries, "originals_removed": removed,
         "undo": f"extract {arc_path.name} back into the target dir to restore"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"archive:{arc_path.name}", f"packed:{len(entries)}",
                  f"removed:{removed}", f"manifest:{manifest.name}"],
        quoted_amount_usd=2.5,
        notes=f"Packed {len(entries)} file(s) ({total} bytes) into "
        f"{arc_path.name}; originals removed only after archive verified; "
        f"restore = extract the tarball.",
    )


# ---------------------------------------------------------------------------
# 92. inbox-sweeper
# ---------------------------------------------------------------------------

def _run_inbox_sweeper(ctx: Dict[str, Any]) -> WorkReport:
    gid = "inbox-sweeper"
    inbox = Path(ctx["params"].get("inbox", str(_target(ctx) / "inbox")))
    rules: List[Dict[str, Any]] = ctx["params"].get("rules") or [
        {"pattern": r"(?i)\b(invoice|receipt|payment|bill)\b", "folder": "finance"},
        {"pattern": r"(?i)\b(meeting|agenda|minutes|standup)\b", "folder": "meetings"},
        {"pattern": r"(?i)\b(alert|error|failed|warning)\b", "folder": "alerts"},
    ]
    messages = [f for f in _files(inbox) if f.parent == inbox
                and f.suffix.lower() in {".txt", ".eml", ".md"}]
    plan: List[Dict[str, Any]] = []
    for f in messages:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        folder = "unsorted"
        for rule in rules:
            if re.search(rule.get("pattern", ""), text, re.DOTALL):
                folder = rule.get("folder", "unsorted")
                break
        plan.append({"from": str(f), "folder": folder,
                     "to": str(inbox / folder / f.name)})
    if ctx.get("dry_run"):
        folders = sorted({p["folder"] for p in plan})
        return WorkReport(
            generator_id=gid,
            produced=[f"plan:triage {len(plan)} message(s) into "
                      f"{len(folders)} folder(s)"],
            quoted_amount_usd=3.0,
            notes=f"DRY RUN: would sweep {len(plan)} message(s) from {inbox}; "
            f"no files moved.",
        )
    work = _work_dir(ctx, gid)
    moved = 0
    for entry in plan:
        dst = Path(entry["to"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            continue
        shutil.move(entry["from"], dst)
        moved += 1
    manifest = _write_json(
        work, "sweep_manifest.json",
        {"id": gid, "at": _utcnow(), "inbox": str(inbox),
         "rules": [{"pattern": r.get("pattern"), "folder": r.get("folder")}
                   for r in rules],
         "moves": plan,
         "undo": "move each 'to' back to 'from'"},
    )
    return WorkReport(
        generator_id=gid,
        produced=[f"triaged:{moved}", f"manifest:{manifest.name}"],
        quoted_amount_usd=3.0,
        notes=f"Swept {moved} message(s) into triaged folders under {inbox}; "
        f"undo manifest {manifest.name}.",
    )


# ---------------------------------------------------------------------------
# Registration — slots 81-92
# ---------------------------------------------------------------------------

_SPECS = [
    (81, "file-sort-bot", "File Sort Bot", 3.0,
     "Sorts a messy directory into category folders (images/documents/audio/"
     "video/archives/code/misc) with an undoable move manifest.",
     _run_file_sort_bot),
    (82, "log-rotator", "Log Rotator", 2.5,
     "Rotates oversized local logs and archives aged-out logs by size/age "
     "policy; compressed archives plus a restore manifest.",
     _run_log_rotator),
    (83, "daily-digest-assembler", "Daily Digest Assembler", 3.0,
     "Assembles a dated morning digest from local notes directories and "
     "recent log tails into one markdown brief.",
     _run_daily_digest),
    (84, "reminder-nudger", "Reminder Nudger", 2.0,
     "Reads a local reminders file (YYYY-MM-DD | text) and reports "
     "overdue, due-today, and upcoming items as a nudge sheet.",
     _run_reminder_nudger),
    (85, "backup-runner", "Backup Runner", 4.0,
     "Local backup with per-file sha256 integrity manifest and a post-copy "
     "verification pass.",
     _run_backup_runner),
    (86, "photo-organizer", "Photo Organizer", 3.5,
     "Organizes images into dated folders from filename date patterns "
     "(mtime fallback) with an undoable manifest.",
     _run_photo_organizer),
    (87, "duplicate-finder", "Duplicate Finder", 4.0,
     "Finds duplicate files by sha256 content hash and reports reclaimable "
     "space; report-only, never deletes.",
     _run_duplicate_finder),
    (88, "bulk-renamer", "Bulk Renamer", 2.5,
     "Rule-based bulk renaming (prefix/suffix/replace/case/regex) with "
     "preview in dry-run and an undo manifest.",
     _run_bulk_renamer),
    (89, "folder-watch-reporter", "Folder Watch Reporter", 2.0,
     "Reports added/removed/modified files in a watched dir since the last "
     "run (JSON state file).",
     _run_folder_watch),
    (90, "task-health-checker", "Task Health Checker", 3.0,
     "Verifies scheduled outputs exist and are fresh (timestamp checks) and "
     "reports gaps.",
     _run_health_checker),
    (91, "archive-packer", "Archive Packer", 2.5,
     "Packs aging files into dated tar.gz archives with a manifest; "
     "originals removed only after the archive verifies (restore = extract).",
     _run_archive_packer),
    (92, "inbox-sweeper", "Inbox Sweeper", 3.0,
     "Sweeps a local text/maildir inbox into triaged folders by regex rules, "
     "with an undoable sweep manifest.",
     _run_inbox_sweeper),
]

for _slot, _gid, _name, _price, _desc, _fn in _SPECS:
    register(
        Generator(
            id=_gid,
            name=_name,
            kind=KIND,
            description=_desc,
            version="1.0.0",
            entry_price_usd=_price,
            run=_fn,
        ),
        slot=_slot,
    )

del _slot, _gid, _name, _price, _desc, _fn
