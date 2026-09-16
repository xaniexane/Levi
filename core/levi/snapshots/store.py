"""Context snapshot engine — capture, resume, list, drop.

A snapshot is a JSON document under ``<LEVI_HOME>/snapshots/<name>.json``:

    {
      "name": str,
      "captured_at": ISO-8601 UTC,
      "focus": str | null,
      "mode": str | null,
      "commitments": [...],        # open commitments (name, streak)
      "tracked_items": [...],      # open tracked items / commitments files
      "repo": {"dir": ..., "branch": ..., "changed": int,
               "untracked": int, "summary": [...]},
      "journal_tail": [...],       # last journal entries
      "notes": [...],              # free-form capture notes
    }

Missing stores are recorded as ``none`` (``"commitments": "none"`` etc.)
rather than invented. Home is resolved at call time from ``LEVI_HOME``
or ``~/.levi``; pass ``home=`` to pin a directory (tests use tmp).
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"
JOURNAL_TAIL_N = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    if home is not None:
        return Path(home)
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding=ENC))
    except (OSError, json.JSONDecodeError):
        return None


def _open_commitments(home: Path) -> Any:
    data = _read_json_file(home / "commitments" / "commitments.json")
    if not data:
        return "none"
    out = []
    items = data if isinstance(data, list) else data.get("commitments", [])
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": item.get("name", "?"),
                "target_per": item.get("target_per"),
                "checkins": len(item.get("checkins") or []),
                "state": item.get("state", "active"),
            }
        )
    return out or "none"


def _open_tracked_items(home: Path) -> Any:
    """Best-effort scan of local tracked-item/commitment-ish stores.

    Tracked items live in the Goals tab product-side; locally we look for
    the files the repo actually writes and mark absence honestly.
    """
    found: List[Dict[str, Any]] = []
    candidates = [
        home / "tracked" / "items.json",
        home / "tracking" / "items.json",
        home / "goals" / "items.json",
    ]
    for path in candidates:
        data = _read_json_file(path)
        if isinstance(data, list) and data:
            found.extend(
                {"name": str(d.get("name", d)) if isinstance(d, dict) else str(d)}
                for d in data
            )
        elif isinstance(data, dict):
            items = data.get("items", [])
            found.extend(
                {"name": str(d.get("name", d)) if isinstance(d, dict) else str(d)}
                for d in items
            )
    return found or "none"


def _journal_tail(home: Path, n: int = JOURNAL_TAIL_N) -> Any:
    path = home / "growth" / "journal.jsonl"
    if not path.exists():
        return "none"
    lines = []
    try:
        with path.open(encoding=ENC) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    lines.append(line)
    except OSError:
        return "none"
    tail = lines[-n:]
    out = []
    for line in tail:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entry = {"raw": line}
        out.append(entry)
    return out or "none"


def _git_summary(repo_dir: "str | os.PathLike[str] | None") -> Any:
    if repo_dir is None:
        cwd = Path(os.getcwd())
        check = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            return "none"
        repo_dir = Path(check.stdout.strip())
    repo = Path(repo_dir)
    if not (repo / ".git").exists():
        return "none"

    def _run(*args: str) -> Optional[str]:
        r = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else None

    branch = _run("branch", "--show-current") or "(detached)"
    porcelain = _run("status", "--porcelain") or ""
    changed, untracked = 0, 0
    summary = []
    for line in porcelain.splitlines():
        if line.startswith("??"):
            untracked += 1
        else:
            changed += 1
        if len(summary) < 10:
            summary.append(line)
    return {
        "dir": str(repo),
        "branch": branch,
        "changed": changed,
        "untracked": untracked,
        "summary": summary,
    }


class SnapshotStore:
    """JSON snapshot persistence under ``<home>/snapshots/``."""

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.home = _resolve_home(home)
        self.root = self.home / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        if not safe:
            raise ValueError("snapshot name must not be empty")
        return self.root / f"{safe}.json"

    def capture(
        self,
        name: str,
        *,
        repo_dir: "str | os.PathLike[str] | None" = None,
        focus: Optional[str] = None,
        mode: Optional[str] = None,
        notes: Optional[List[str]] = None,
        journal_n: int = JOURNAL_TAIL_N,
    ) -> Dict[str, Any]:
        """Capture full working state into a named snapshot (overwrites)."""
        if focus is None:
            stored = _read_json_file(self.root / "current_focus.json")
            focus = stored.get("focus") if isinstance(stored, dict) else None
        snap = {
            "name": name,
            "captured_at": _now_iso(),
            "focus": focus,
            "mode": mode,
            "commitments": _open_commitments(self.home),
            "tracked_items": _open_tracked_items(self.home),
            "repo": _git_summary(repo_dir),
            "journal_tail": _journal_tail(self.home, journal_n),
            "notes": list(notes or []),
        }
        self._path(name).write_text(
            json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding=ENC
        )
        return snap

    def resume(self, name: str) -> Dict[str, Any]:
        """Return the snapshot document; raises KeyError when unknown."""
        path = self._path(name)
        if not path.exists():
            raise KeyError(f"no snapshot named {name!r}")
        return json.loads(path.read_text(encoding=ENC))

    def list_snapshots(self) -> List[Dict[str, str]]:
        out = []
        for path in sorted(self.root.glob("*.json")):
            if path.name == "current_focus.json":
                continue
            try:
                doc = json.loads(path.read_text(encoding=ENC))
            except (OSError, json.JSONDecodeError):
                continue
            out.append({"name": path.stem, "captured_at": doc.get("captured_at", "?")})
        return sorted(out, key=lambda d: d["captured_at"])

    def drop(self, name: str) -> bool:
        """Delete a snapshot; returns True when something was removed."""
        path = self._path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def set_focus(self, focus: Optional[str]) -> None:
        """Persist the current focus so future captures pick it up."""
        (self.root / "current_focus.json").write_text(
            json.dumps({"focus": focus, "set_at": _now_iso()}, indent=2) + "\n",
            encoding=ENC,
        )


# -- module-level convenience wrappers (home resolved at call time) --------


def capture(name: str, **kwargs: Any) -> Dict[str, Any]:
    return SnapshotStore().capture(name, **kwargs)


def resume(name: str) -> Dict[str, Any]:
    return SnapshotStore().resume(name)


def list_snapshots() -> List[Dict[str, str]]:
    return SnapshotStore().list_snapshots()


def drop(name: str) -> bool:
    return SnapshotStore().drop(name)


def resume_brief(snap: Dict[str, Any]) -> str:
    """Render a human-readable resume brief from a snapshot document."""
    lines = [
        f"resume brief — snapshot '{snap.get('name', '?')}' "
        f"(captured {snap.get('captured_at', '?')})",
        "",
    ]
    focus, mode = snap.get("focus"), snap.get("mode")
    lines.append(f"focus: {focus or '—'}    mode: {mode or '—'}")
    lines.append("")

    commitments = snap.get("commitments")
    if commitments == "none":
        lines.append("commitments: none recorded")
    else:
        lines.append("open commitments:")
        for c in commitments:
            lines.append(
                f"  - {c.get('name')} (target_per={c.get('target_per')}, "
                f"checkins={c.get('checkins')}, state={c.get('state')})"
            )

    tracked = snap.get("tracked_items")
    if tracked == "none":
        lines.append("tracked items: none recorded")
    else:
        lines.append("tracked items:")
        for t in tracked:
            lines.append(f"  - {t.get('name')}")

    repo = snap.get("repo")
    if repo == "none":
        lines.append("repo: not a git repo / unavailable")
    else:
        lines.append(
            f"repo: {repo.get('dir')} @ {repo.get('branch')} — "
            f"{repo.get('changed')} changed, {repo.get('untracked')} untracked"
        )
        for s in repo.get("summary", []):
            lines.append(f"    {s}")

    journal = snap.get("journal_tail")
    if journal == "none":
        lines.append("journal: no recent entries")
    else:
        lines.append("recent journal entries:")
        for e in journal:
            txt = e.get("entry") or e.get("text") or e.get("raw") or str(e)
            lines.append(f"  - {txt}")

    notes = snap.get("notes") or []
    if notes:
        lines.append("capture notes:")
        for n in notes:
            lines.append(f"  - {n}")

    lines.append("")
    lines.append(
        "what was next: pick up the focus above; "
        "commitments/tracked items listed are still open."
    )
    return "\n".join(lines)
