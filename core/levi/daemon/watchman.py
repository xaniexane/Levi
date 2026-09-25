"""Directory watchman — a small polling file watcher for the daemon layer.

LEVI-native and stdlib-only: no inotify/watchdog dependency. ``Watchman``
snapshots ``(mtime_ns, size)`` per file under configured roots and reports
``created`` / ``modified`` / ``deleted`` events on each ``watch_once()``
tick. Events are appended to an owner-only JSONL journal so other LEVI
components (automation, growth, the Archive) can consume them later.

Stop semantics: ``run()`` loops ``watch_once()`` every ``interval_sec``
until ``stop()`` is called or a stop-file appears. There is no daemonize
here — the long-run entry is ``python3 -m levi.daemon.watchman`` inside
the perpetual supervisor (one_for_one child), or a plain thread via
``run_in_thread()``.
"""

from __future__ import annotations

import fnmatch
import json
import os
import stat
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_STATE_PATH = Path.home() / ".levi" / "watchman" / "state.json"
DEFAULT_JOURNAL_PATH = Path.home() / ".levi" / "watchman" / "events.jsonl"

#: Events we never emit — LEVI's own state churn.
_DEFAULT_IGNORES = (".levi", "__pycache__", ".git")


@dataclass
class WatchEvent:
    kind: str  # created | modified | deleted
    path: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WatchmanConfig:
    roots: List[str] = field(default_factory=list)
    interval_sec: float = 5.0
    ignore: List[str] = field(default_factory=lambda: list(_DEFAULT_IGNORES))
    follow_symlinks: bool = False
    state_path: str = str(DEFAULT_STATE_PATH)
    journal_path: str = str(DEFAULT_JOURNAL_PATH)
    stop_file: str = ""  # optional: path whose appearance stops run()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WatchmanConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def _matches(path: Path, patterns: Iterable[str]) -> bool:
    rel = str(path)
    return any(fnmatch.fnmatch(rel, p) or p in path.parts for p in patterns)


def _snapshot(
    root: Path, ignore: Iterable[str], follow_symlinks: bool
) -> Dict[str, List[int]]:
    """Map relative file path -> [mtime_ns, size]. Directories are skipped."""
    snap: Dict[str, List[int]] = {}
    if not root.is_dir():
        return snap
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        d = Path(dirpath)
        # Prune ignored directories before descending.
        dirnames[:] = [x for x in dirnames if not _matches(d / x, ignore)]
        for name in filenames:
            p = d / name
            if _matches(p, ignore):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            snap[str(p.relative_to(root))] = [st.st_mtime_ns, st.st_size]
    return snap


class Watchman:
    """Polling directory watcher with persistent baseline + JSONL journal."""

    def __init__(self, config: Optional[WatchmanConfig] = None) -> None:
        self.config = config or WatchmanConfig()
        self._stop = threading.Event()
        self._baseline: Dict[str, Dict[str, List[int]]] = {}
        self._load_state()

    # -- persistence ------------------------------------------------------

    def _load_state(self) -> None:
        try:
            raw = json.loads(Path(self.config.state_path).read_text())
            if isinstance(raw, dict):
                self._baseline = raw
        except (OSError, ValueError):
            self._baseline = {}

    def _save_state(self) -> None:
        path = Path(self.config.state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._baseline, indent=1))
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # -- journal ----------------------------------------------------------

    def _journal(self, events: List[WatchEvent]) -> None:
        if not events:
            return
        path = Path(self.config.journal_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev.to_dict()) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # -- core tick --------------------------------------------------------

    def watch_once(self) -> List[WatchEvent]:
        """Diff every root against the baseline; return and journal events."""
        events: List[WatchEvent] = []
        new_baseline: Dict[str, Dict[str, List[int]]] = {}
        for root_str in self.config.roots:
            root = Path(root_str).expanduser()
            snap = _snapshot(root, self.config.ignore, self.config.follow_symlinks)
            old = self._baseline.get(root_str)
            if old is None:
                # First sight of this root: establish the baseline silently.
                # Emitting "created" for everything already on disk would
                # flood the journal (and any automation listening to it).
                new_baseline[root_str] = snap
                continue
            for rel, meta in snap.items():
                prev = old.get(rel)
                if prev is None:
                    events.append(
                        WatchEvent(
                            "created", f"{root_str}/{rel}", detail={"size": meta[1]}
                        )
                    )
                elif prev != meta:
                    events.append(
                        WatchEvent(
                            "modified", f"{root_str}/{rel}", detail={"size": meta[1]}
                        )
                    )
            for rel in old:
                if rel not in snap:
                    events.append(WatchEvent("deleted", f"{root_str}/{rel}"))
            new_baseline[root_str] = snap
        self._baseline = new_baseline
        self._save_state()
        self._journal(events)
        return events

    # -- long run ---------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()

    def _stop_requested(self) -> bool:
        if self._stop.is_set():
            return True
        if self.config.stop_file and Path(self.config.stop_file).exists():
            return True
        return False

    def run(self) -> int:
        """Tick until stopped. Returns the number of events observed."""
        total = 0
        while not self._stop_requested():
            total += len(self.watch_once())
            self._stop.wait(self.config.interval_sec)
        return total

    def run_in_thread(self, **kwargs: Any) -> threading.Thread:
        """Run the watchman in a background daemon thread."""
        t = threading.Thread(
            target=self.run, kwargs=kwargs, daemon=True, name="levi-watchman"
        )
        t.start()
        return t


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="LEVI directory watchman")
    ap.add_argument(
        "--root", action="append", default=[], help="Directory to watch (repeatable)"
    )
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Extra ignore pattern (repeatable)",
    )
    ap.add_argument("--stop-file", default="")
    ap.add_argument(
        "--once",
        action="store_true",
        help="Single tick: print events as JSON, then exit",
    )
    args = ap.parse_args()

    cfg = WatchmanConfig(
        roots=args.root,
        interval_sec=args.interval,
        ignore=list(_DEFAULT_IGNORES) + args.ignore,
        stop_file=args.stop_file,
    )
    wm = Watchman(cfg)
    if args.once:
        print(json.dumps([e.to_dict() for e in wm.watch_once()], indent=1))
        return 0
    return wm.run()


if __name__ == "__main__":
    raise SystemExit(main())
