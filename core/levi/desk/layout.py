"""The layout: which tiles sit on the desk, in what order, with whose prefs.

``~/.levi/desk/layout.json`` is a JSON array of::

    {"tile": name, "enabled": bool, "prefs": {...}}

The registry decides what exists; the layout decides what shows. A layout
entry pointing at an unknown tile is reported, not crashed on — the user
may have deregistered a module.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .registry import TileError

HOME_DIRNAME = ".levi"
SUBDIR = "desk"


def _home(base: Optional[Path] = None) -> Path:
    d = (base or Path.home()) / HOME_DIRNAME / SUBDIR
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class DeskLayout:
    """The user's arrangement. Order is the layout order; gaps are kept."""

    def __init__(self, base: Optional[Path] = None) -> None:
        self._dir = _home(base)
        self._file = self._dir / "layout.json"
        self._entries: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            self._entries = []
            return
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            self._entries = []
            return
        if not isinstance(data, list):
            self._entries = []
            return
        clean: List[Dict] = []
        for e in data:
            if not isinstance(e, dict):
                continue
            name = e.get("tile")
            if not isinstance(name, str) or not name:
                continue
            prefs = e.get("prefs")
            clean.append({
                "tile": name,
                "enabled": bool(e.get("enabled", True)),
                "prefs": dict(prefs) if isinstance(prefs, dict) else {},
            })
        self._entries = clean

    def _save(self) -> None:
        _atomic_write(self._file, json.dumps(self._entries, indent=1) + "\n")

    def entries(self) -> List[Dict]:
        return [dict(e) for e in self._entries]

    def add(self, name: str, prefs: Optional[Dict] = None,
            position: Optional[int] = None) -> None:
        if any(e["tile"] == name for e in self._entries):
            raise TileError("tile already on the desk: %r" % (name,))
        entry = {"tile": name, "enabled": True,
                 "prefs": dict(prefs) if prefs else {}}
        if position is None or position >= len(self._entries):
            self._entries.append(entry)
        else:
            self._entries.insert(max(0, position), entry)
        self._save()

    def remove(self, name: str) -> None:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["tile"] != name]
        if len(self._entries) == before:
            raise TileError("tile not on the desk: %r" % (name,))
        self._save()

    def move(self, name: str, position: int) -> None:
        idx = next((i for i, e in enumerate(self._entries)
                    if e["tile"] == name), None)
        if idx is None:
            raise TileError("tile not on the desk: %r" % (name,))
        entry = self._entries.pop(idx)
        self._entries.insert(max(0, min(position, len(self._entries))), entry)
        self._save()

    def set_enabled(self, name: str, enabled: bool) -> None:
        for e in self._entries:
            if e["tile"] == name:
                e["enabled"] = bool(enabled)
                self._save()
                return
        raise TileError("tile not on the desk: %r" % (name,))

    def set_prefs(self, name: str, prefs: Dict) -> None:
        for e in self._entries:
            if e["tile"] == name:
                e["prefs"] = dict(prefs)
                self._save()
                return
        raise TileError("tile not on the desk: %r" % (name,))
