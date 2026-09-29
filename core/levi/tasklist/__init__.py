"""LEVI tasklist — honest shared task lists that no giant can kill.

REMIX DELTA: Wunderlist (2011-2020) put the shared list with subtasks in
everyone's pocket, then Microsoft bought it and starved it to death to
feed the flagship — the flagship-sacrifice pattern (perpetual-hunt wave
``evening-20260927-flagship-sacrifice``). The remix inverts the bargain:
the shared list with steps lives as a portable plain file in an
owner-only local store. Sharing = handing someone the file. No account,
no subscription, no backend that stops syncing on May 6th of some year.

What it ADDS that the giants refuse:
- Lists with subtasks (steps), priorities, due dates, notes — first-class.
- Done receipts: completing a task writes an append-only receipt; nothing
  is ever deleted (nothing-thrown-away law). A done task can be reopened.
- Portable share files: a list exports to ONE plain JSON file; anyone who
  receives it can import it and keep working — the list outlives any server.
- Zero network, zero accounts, stdlib only. Privacy is architectural.

LAWS (invariants; every write path defends them):
- L1 COMPLETE-NEVER-DELETE: completing or removing a task appends a
  receipt carrying the task's full record; the record is restorable.
- L2 OWNER-ONLY: store dir is 0o700, every file 0o600. No exceptions.
- L3 LOSSLESS-PORTABILITY: export_list() then import_list() reproduces the
  source list exactly (tasks, steps, receipts of completed tasks included).
- L4 NO-SILENT-DUPLICATES: creating a list or task whose id already exists
  is refused, never merged or overwritten.

Run: ``python -m levi.tasklist --help``
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "TaskLists",
    "PRIORITIES",
    "home_dir",
    "TaskError",
]

PRIORITIES = ("low", "normal", "high", "urgent")


class TaskError(ValueError):
    """Any refusal: duplicates, unknown ids, bad dates, bad priorities."""


def home_dir() -> Path:
    """Tasklist home: ``~/.levi/tasklist`` or ``LEVI_TASKLIST_DIR``."""
    override = os.environ.get("LEVI_TASKLIST_DIR")
    base = Path(override).expanduser() if override else Path.home() / ".levi" / "tasklist"
    base.mkdir(parents=True, exist_ok=True)
    _lock_down(base)
    return base


def _lock_down(path: Path) -> None:
    """L2: owner-only permissions, enforced on every store touch."""
    if path.is_dir():
        os.chmod(path, 0o700)
    else:
        os.chmod(path, 0o600)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "list"


def _check_due(due: Optional[str]) -> Optional[str]:
    if due is None:
        return None
    try:
        date.fromisoformat(due)
    except ValueError as exc:
        raise TaskError(f"bad due date {due!r}: expected YYYY-MM-DD") from exc
    return due


def _check_priority(priority: str) -> str:
    if priority not in PRIORITIES:
        raise TaskError(f"bad priority {priority!r}: expected one of {PRIORITIES}")
    return priority


def _new_task(title: str, **opts: Any) -> Dict[str, Any]:
    if not title or not title.strip():
        raise TaskError("task title may not be empty")
    return {
        "id": opts.get("id") or f"t-{uuid.uuid4().hex[:12]}",
        "title": title.strip(),
        "notes": str(opts.get("notes") or ""),
        "priority": _check_priority(opts.get("priority") or "normal"),
        "due": _check_due(opts.get("due")),
        "tags": list(opts.get("tags") or []),
        "steps": [],  # [{"id":..., "title":..., "done":bool}]
        "status": "open",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


class TaskLists:
    """Owner-side task lists. All state under ``home_dir()``; stdlib only."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home or home_dir()
        self.lists_dir = self.home / "lists"
        self.lists_dir.mkdir(parents=True, exist_ok=True)
        _lock_down(self.lists_dir)
        self.receipts_path = self.home / "receipts.jsonl"
        _lock_down(self.home)

    # -- storage internals -------------------------------------------------
    def _path(self, name: str) -> Path:
        return self.lists_dir / f"{_slug(name)}.json"

    def _load(self, name: str) -> Dict[str, Any]:
        path = self._path(name)
        if not path.exists():
            raise TaskError(f"no such list: {name!r}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, data: Dict[str, Any]) -> None:
        path = self._path(data["name"])
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        _lock_down(path)

    def _receipt(self, action: str, list_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """L1: every terminal state change carries the full task record."""
        entry = {
            "action": action,
            "list": list_name,
            "at": _now_iso(),
            "task": dict(task),
        }
        with self.receipts_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        _lock_down(self.receipts_path)
        return entry

    def _find_task(self, data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        for task in data["tasks"]:
            if task["id"] == task_id:
                return task
        raise TaskError(f"no such task {task_id!r} in list {data['name']!r}")

    # -- lists --------------------------------------------------------------
    def create_list(self, name: str) -> Dict[str, Any]:
        path = self._path(name)
        if path.exists():
            raise TaskError(f"list {name!r} already exists")  # L4
        data = {"name": name, "slug": _slug(name), "created_at": _now_iso(), "tasks": []}
        self._save(data)
        return data

    def rename_list(self, old: str, new: str) -> Dict[str, Any]:
        data = self._load(old)
        if self._path(new).exists():
            raise TaskError(f"list {new!r} already exists")  # L4
        data["name"] = new
        data["slug"] = _slug(new)
        self._path(old).unlink()
        self._save(data)
        return data

    def lists(self) -> List[str]:
        names = []
        for path in sorted(self.lists_dir.glob("*.json")):
            try:
                names.append(json.loads(path.read_text(encoding="utf-8"))["name"])
            except (OSError, ValueError, KeyError):
                continue
        return names

    # -- tasks --------------------------------------------------------------
    def add_task(self, list_name: str, title: str, **opts: Any) -> Dict[str, Any]:
        data = self._load(list_name)
        task = _new_task(title, **opts)
        if any(t["id"] == task["id"] for t in data["tasks"]):
            raise TaskError(f"task id {task['id']!r} already in list")  # L4
        data["tasks"].append(task)
        self._save(data)
        return task

    def get_task(self, list_name: str, task_id: str) -> Dict[str, Any]:
        return self._find_task(self._load(list_name), task_id)

    def update_task(self, list_name: str, task_id: str, **fields: Any) -> Dict[str, Any]:
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        for key in ("title", "notes"):
            if key in fields:
                task[key] = str(fields[key])
        if "priority" in fields:
            task["priority"] = _check_priority(fields["priority"])
        if "due" in fields:
            task["due"] = _check_due(fields["due"])
        if "tags" in fields:
            task["tags"] = list(fields["tags"])
        task["updated_at"] = _now_iso()
        self._save(data)
        return task

    def complete_task(self, list_name: str, task_id: str) -> Dict[str, Any]:
        """Mark done and append a done receipt (L1). The task stays restorable."""
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        task["status"] = "done"
        task["updated_at"] = _now_iso()
        self._save(data)
        return self._receipt("completed", list_name, task)

    def reopen_task(self, list_name: str, task_id: str) -> Dict[str, Any]:
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        if task["status"] != "done":
            raise TaskError(f"task {task_id!r} is not done")
        task["status"] = "open"
        task["updated_at"] = _now_iso()
        self._save(data)
        return self._receipt("reopened", list_name, task)

    def remove_task(self, list_name: str, task_id: str) -> Dict[str, Any]:
        """Remove from the list, but the receipt keeps the full record (L1)."""
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        self._save(data)
        return self._receipt("removed", list_name, task)

    # -- steps (Wunderlist's load-bearing social object, local form) ---------
    def add_step(self, list_name: str, task_id: str, title: str) -> Dict[str, Any]:
        if not title or not title.strip():
            raise TaskError("step title may not be empty")
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        step = {"id": f"s-{uuid.uuid4().hex[:12]}", "title": title.strip(), "done": False}
        task["steps"].append(step)
        task["updated_at"] = _now_iso()
        self._save(data)
        return step

    def set_step(self, list_name: str, task_id: str, step_id: str, done: bool) -> Dict[str, Any]:
        data = self._load(list_name)
        task = self._find_task(data, task_id)
        for step in task["steps"]:
            if step["id"] == step_id:
                step["done"] = bool(done)
                task["updated_at"] = _now_iso()
                self._save(data)
                return step
        raise TaskError(f"no such step {step_id!r}")

    # -- views ---------------------------------------------------------------
    def open_tasks(self, list_name: str) -> List[Dict[str, Any]]:
        return [t for t in self._load(list_name)["tasks"] if t["status"] == "open"]

    def due_today(self, list_name: str) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        return [t for t in self.open_tasks(list_name) if t["due"] == today]

    def overdue(self, list_name: str) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        return [t for t in self.open_tasks(list_name) if t["due"] and t["due"] < today]

    def by_priority(self, list_name: str) -> List[Dict[str, Any]]:
        rank = {p: i for i, p in enumerate(reversed(PRIORITIES))}
        return sorted(self.open_tasks(list_name), key=lambda t: rank[t["priority"]])

    def search(self, list_name: str, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        return [
            t
            for t in self._load(list_name)["tasks"]
            if q in t["title"].lower() or q in t["notes"].lower()
            or any(q in s["title"].lower() for s in t["steps"])
        ]

    def receipts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.receipts_path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self.receipts_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return rows[-limit:] if limit else rows

    # -- portability (L3: the share file IS the list) -------------------------
    def export_list(self, list_name: str, dest: Path) -> Path:
        """Export one list to a single portable JSON file. Sharing = handing
        someone this file; no intermediary, no account, no backend to kill."""
        data = self._load(list_name)
        payload = {
            "levi_tasklist_share": 1,
            "exported_at": _now_iso(),
            "list": data,
            "receipts": [r for r in self.receipts() if r["list"] == list_name],
        }
        dest = Path(dest)
        dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(dest, 0o600)
        return dest

    def import_list(self, src: Path) -> Dict[str, Any]:
        """Import a share file. L3: byte-identical round trip; L4: collisions
        refused, never merged."""
        payload = json.loads(Path(src).read_text(encoding="utf-8"))
        if payload.get("levi_tasklist_share") != 1 or "list" not in payload:
            raise TaskError(f"not a tasklist share file: {src}")
        data = payload["list"]
        if self._path(data["name"]).exists():
            raise TaskError(f"list {data['name']!r} already exists")  # L4
        for task in data["tasks"]:
            task.setdefault("steps", [])
        self._save(data)
        if payload.get("receipts"):
            with self.receipts_path.open("a", encoding="utf-8") as fh:
                for entry in payload["receipts"]:
                    fh.write(json.dumps(entry, sort_keys=True) + "\n")
            _lock_down(self.receipts_path)
        return data
