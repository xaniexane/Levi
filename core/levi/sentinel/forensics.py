"""Sentinel forensics — defensive case management.

Case directory tree, append-only chain-of-custody log, path hashing, and
a markdown case summary. Local-only, no network, no automation of
destructive acts.

Stdlib-only: ``hashlib``, ``json``, ``os``, ``time``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "Case",
    "create_case",
    "open_case",
    "CASE_DIRS",
    "default_cases_root",
]

#: Standard case tree layout.
CASE_DIRS = ("evidence", "exports", "logs", "reports")


def default_cases_root() -> Path:
    root = Path.home() / ".levi" / "sentinel" / "cases"
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class Case:
    """A forensic case directory with an append-only custody log."""

    name: str
    path: Path
    created: float = field(default_factory=time.time)

    # -- chain of custody ------------------------------------------------

    def _custody_path(self) -> Path:
        return self.path / "logs" / "chain_of_custody.jsonl"

    def log(self, event: str, detail: Optional[Dict[str, object]] = None) -> None:
        """Append one custody event. Append-only — never edits history."""
        record = {
            "ts": time.time(),
            "event": event,
            "detail": detail or {},
        }
        with self._custody_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def custody_events(self) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        try:
            for line in self._custody_path().read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        except (OSError, ValueError):
            pass
        return events

    # -- evidence hashing ------------------------------------------------

    def hash_path(self, target: str) -> Dict[str, str]:
        """SHA-256 every file under ``target`` into the case exports dir.

        Read-only on the target; the hash list is evidence, not action.
        """
        target_p = Path(target)
        if not target_p.exists():
            raise ValueError(f"no such path: {target}")
        out = self.path / "exports" / f"hashes_{int(time.time())}.txt"
        hashes: Dict[str, str] = {}
        if target_p.is_file():
            files = [target_p]
        else:
            files = []
            for dirpath, _dirnames, filenames in os.walk(target_p):
                for fname in sorted(filenames):
                    files.append(Path(dirpath) / fname)
        lines = []
        for full in files[:2000]:
            digest = hashlib.sha256()
            try:
                with full.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        digest.update(chunk)
            except OSError:
                continue
            hexsum = digest.hexdigest()
            hashes[str(full)] = hexsum
            lines.append(f"{hexsum}  {full}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log(
            "hash_path",
            {"target": str(target_p), "files": len(hashes), "manifest": str(out)},
        )
        return hashes

    # -- reporting -------------------------------------------------------

    def write_summary(self, title: str = "Case summary") -> Path:
        """Write a markdown case summary (analyst fills in findings)."""
        rpt = self.path / "reports" / "case_summary.md"
        events = self.custody_events()
        body = [
            f"# {title}",
            "",
            f"- **Case:** {self.name}",
            f"- **Path:** {self.path}",
            f"- **Created:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.created))}",
            f"- **Custody events:** {len(events)}",
            "",
            "## Authorization",
            "",
            "State ownership or written authority for this investigation.",
            "",
            "## Findings",
            "",
            "Add findings, hashes, and tool outputs here.",
            "",
            "## Chain of custody",
            "",
        ]
        for event in events:
            ts = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(float(event.get("ts", 0)))
            )
            body.append(f"- {ts} — {event.get('event')}")
        rpt.write_text("\n".join(body) + "\n", encoding="utf-8")
        return rpt


def create_case(name: str, root: Optional[Path] = None) -> Case:
    """Create a new case tree. ``name`` must be a safe slug."""
    slug = "".join(
        ch
        for ch in name.strip().lower().replace(" ", "_")
        if ch.isalnum() or ch in ("_", "-")
    )
    if not slug:
        raise ValueError("case name must contain letters or digits")
    base = Path(root) if root else default_cases_root()
    case_path = base / f"{time.strftime('%Y%m%d_%H%M%S')}_{slug}"
    for sub in CASE_DIRS:
        (case_path / sub).mkdir(parents=True, exist_ok=True)
    case = Case(name=slug, path=case_path)
    case.log("case_created", {"name": slug})
    return case


def open_case(case_dir: str) -> Case:
    """Re-open an existing case directory."""
    path = Path(case_dir)
    if not path.is_dir():
        raise ValueError(f"not a case directory: {case_dir}")
    return Case(name=path.name, path=path)
