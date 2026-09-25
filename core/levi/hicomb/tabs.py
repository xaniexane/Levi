"""Multi-tab session: the daemon owns the state, the UI only renders.

Open a folder -> Hicomb finds the .git (or offers init/clone in Phase 1)
and the project IS a repo. Session state serializes to local JSON so
continuity survives app kills, phone swaps, and reinstalls — the daemon's
memory, not the UI process's. Projects live in the user's tree: uninstall
the UI and the code is still there (the opposite of Spck's warning).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from levi.hicomb.buffer import Buffer, BufferError
from levi.hicomb.highlight import detect_language

SESSION_VERSION = 1
TREE_MAX_DEPTH = 6
TREE_MAX_ENTRIES = 4000


class SessionError(Exception):
    """Tab/session misuse: bad index, dirty close, unknown path."""


@dataclass
class Tab:
    path: str | None
    buffer: Buffer
    language: str = "plain"

    @property
    def title(self) -> str:
        if self.path:
            return os.path.basename(self.path)
        return "untitled"

    @property
    def dirty(self) -> bool:
        return self.buffer.dirty


def file_tree(root: str, max_depth: int = TREE_MAX_DEPTH) -> dict:
    """Nested file tree. Deterministic, depth-capped, skips VCS dirs."""
    skip = {".git", ".hg", ".svn", "__pycache__", ".hicomb", "node_modules"}
    count = 0

    def walk(path: str, depth: int) -> dict | None:
        nonlocal count
        name = os.path.basename(path) or path
        if os.path.isdir(path):
            if depth > max_depth:
                return {
                    "name": name,
                    "path": path,
                    "type": "dir",
                    "children": [],
                    "truncated": True,
                }
            children = []
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                entries = []
            for entry in entries:
                if entry in skip or entry.startswith(".hicomb"):
                    continue
                child = walk(os.path.join(path, entry), depth + 1)
                if child is not None:
                    children.append(child)
                    count += 1
                    if count >= TREE_MAX_ENTRIES:
                        break
            return {"name": name, "path": path, "type": "dir", "children": children}
        count += 1
        return {"name": name, "path": path, "type": "file"}

    return walk(os.path.abspath(root), 0) or {}


def detect_repo(root: str) -> dict:
    """What kind of project is this folder? .git detection for Phase 1."""
    root = os.path.abspath(root)
    git_dir = os.path.join(root, ".git")
    info: dict = {"root": root, "is_repo": False, "vcs": None, "branch": None}
    if os.path.isdir(git_dir):
        info["is_repo"] = True
        info["vcs"] = "git"
        head = os.path.join(git_dir, "HEAD")
        try:
            with open(head, encoding="utf-8") as fh:
                ref = fh.read().strip()
            if ref.startswith("ref:"):
                info["branch"] = ref.split("/")[-1]
        except OSError:
            pass
    return info


class Session:
    """The editor session: tabs, open folder, extensions, saved state."""

    def __init__(self) -> None:
        self.tabs: list[Tab] = []
        self.active_index: int = -1
        self.folder: str | None = None
        self.repo: dict = {}
        self.extensions: dict = {}  # dock point for builders etc.

    # ---------------------------------------------------------------- tabs
    @property
    def active(self) -> Tab | None:
        if 0 <= self.active_index < len(self.tabs):
            return self.tabs[self.active_index]
        return None

    def open_tab(self, path: str | None = None) -> Tab:
        """Open a file tab (or a fresh untitled tab). Reuses existing tab."""
        if path is not None:
            apath = os.path.abspath(path)
            for i, tab in enumerate(self.tabs):
                if tab.path and os.path.abspath(tab.path) == apath:
                    self.active_index = i
                    return tab
            buf = Buffer.open(apath) if os.path.exists(apath) else Buffer(path=apath)
            tab = Tab(path=apath, buffer=buf, language=detect_language(apath))
        else:
            tab = Tab(path=None, buffer=Buffer())
        self.tabs.append(tab)
        self.active_index = len(self.tabs) - 1
        return tab

    def close_tab(self, index: int | None = None, force: bool = False) -> bool:
        """Close a tab. Refuses dirty tabs unless force=True."""
        idx = self.active_index if index is None else index
        if not 0 <= idx < len(self.tabs):
            raise SessionError(f"no tab at index {idx}")
        if self.tabs[idx].dirty and not force:
            raise SessionError("tab has unsaved changes (use force=True)")
        del self.tabs[idx]
        if self.active_index >= len(self.tabs):
            self.active_index = len(self.tabs) - 1
        elif self.active_index > idx:
            self.active_index -= 1
        return True

    def switch_tab(self, index: int) -> Tab:
        if not 0 <= index < len(self.tabs):
            raise SessionError(f"no tab at index {index}")
        self.active_index = index
        return self.tabs[index]

    def save_active(self, path: str | None = None) -> str:
        tab = self.active
        if tab is None:
            raise SessionError("no active tab")
        saved = tab.buffer.save(path)
        tab.path = saved
        tab.language = detect_language(saved)
        return saved

    # --------------------------------------------------------------- folder
    def open_folder(self, root: str) -> dict:
        """Open a project folder. The project IS a repo (or will be)."""
        if not os.path.isdir(root):
            raise SessionError(f"not a folder: {root}")
        self.folder = os.path.abspath(root)
        self.repo = detect_repo(self.folder)
        return self.repo

    def tree(self) -> dict:
        if self.folder is None:
            raise SessionError("no folder open")
        return file_tree(self.folder)

    # ---------------------------------------------------------------- state
    def to_state(self) -> dict:
        """JSON-serializable session state. Local-first continuity."""
        return {
            "version": SESSION_VERSION,
            "folder": self.folder,
            "tabs": [t.path for t in self.tabs if t.path],
            "active": self.active_index,
        }

    def save_state(self, path: str) -> str:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_state(), fh, indent=2, sort_keys=True)
        return path

    @classmethod
    def load_state(cls, path: str) -> "Session":
        """Restore a session. Missing files are skipped, never fatal."""
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        if state.get("version") != SESSION_VERSION:
            raise SessionError(f"unsupported session version: {state.get('version')}")
        sess = cls()
        folder = state.get("folder")
        if folder and os.path.isdir(folder):
            sess.open_folder(folder)
        for tab_path in state.get("tabs", []):
            if tab_path and os.path.exists(tab_path):
                try:
                    sess.open_tab(tab_path)
                except BufferError:
                    continue  # binary etc. — skip, don't die
        active = state.get("active", -1)
        if 0 <= active < len(sess.tabs):
            sess.active_index = active
        elif sess.tabs:
            sess.active_index = 0
        return sess

    def recent_files(self, limit: int = 20) -> list[str]:
        """Most-recently-opened files, active tab last (MRU order)."""
        paths = [t.path for t in self.tabs if t.path]
        if self.active is not None and self.active.path in paths:
            paths.remove(self.active.path)
            paths.append(self.active.path)
        return paths[-limit:]
