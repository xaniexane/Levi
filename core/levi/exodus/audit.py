"""Takeout export auditor: trust, but verify.

Giants ship export tools that are theater — HTML-only dumps, missing media,
machine-unreadable formats. This auditor inspects a downloaded takeout
(directory or .zip) and reports honestly what it covers: formats present,
what's machine-readable, red flags. It never claims completeness it can't
prove.
"""

from __future__ import annotations

import os
import zipfile
from typing import Dict, List

MACHINE_READABLE = {".json", ".csv", ".jsonl", ".xml", ".txt", ".md"}
THEATER_FORMATS = {".html", ".htm"}  # readable by eye, hostile to machines
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mp3", ".webp", ".webm"}


def _walk_zip(path: str) -> List[str]:
    with zipfile.ZipFile(path) as zf:
        return [i.filename for i in zf.infolist() if not i.is_dir()]


def _walk_dir(path: str) -> List[str]:
    out: List[str] = []
    for root, _dirs, files in os.walk(path):
        for f in files:
            out.append(os.path.relpath(os.path.join(root, f), path))
    return out


def audit_export(path: str) -> Dict[str, object]:
    """Audit a takeout export. Returns an honest report dict."""
    report: Dict[str, object] = {
        "path": path,
        "files": 0,
        "formats": {},
        "machine_readable_files": 0,
        "theater_files": 0,
        "media_files": 0,
        "red_flags": [],
    }
    if os.path.isdir(path):
        files = _walk_dir(path)
    elif os.path.isfile(path) and zipfile.is_zipfile(path):
        files = _walk_zip(path)
    else:
        report["red_flags"] = ["not a directory or zip file: %r" % path]
        return report

    formats: Dict[str, int] = {}
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        formats[ext or "(none)"] = formats.get(ext or "(none)", 0) + 1
        if ext in MACHINE_READABLE:
            report["machine_readable_files"] = int(report["machine_readable_files"]) + 1
        if ext in THEATER_FORMATS:
            report["theater_files"] = int(report["theater_files"]) + 1
        if ext in MEDIA_EXTS:
            report["media_files"] = int(report["media_files"]) + 1
    report["files"] = len(files)
    report["formats"] = formats

    flags = report["red_flags"]
    assert isinstance(flags, list)
    if not files:
        flags.append("export is empty")
    if int(report["theater_files"]) and not int(report["machine_readable_files"]):
        flags.append(
            "export-theater: %d HTML files, zero machine-readable files — "
            "readable by eye, hostile to machines" % int(report["theater_files"])
        )
    if int(report["files"]) and not int(report["media_files"]):
        flags.append(
            "no media files found — attachments may have been stripped"
        )
    return report


def audit_to_text(report: Dict[str, object]) -> str:
    """One-glance honest summary."""
    lines = [
        "takeout audit: %s" % report["path"],
        "files: %d | machine-readable: %d | html-theater: %d | media: %d"
        % (report["files"], report["machine_readable_files"],
           report["theater_files"], report["media_files"]),
        "formats: %s" % ", ".join(
            "%s x%d" % (k, v) for k, v in sorted(report["formats"].items())),
    ]
    flags = report["red_flags"]
    assert isinstance(flags, list)
    if flags:
        lines.append("RED FLAGS:")
        lines += ["- %s" % f for f in flags]
    else:
        lines.append("no red flags — export looks honest (coverage still not proven)")
    return "\n".join(lines)
