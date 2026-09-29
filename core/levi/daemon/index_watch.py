"""LEVI index-integrity watch daemon.

Watches the shared git index (``~/workspace/levi/.git/index``) for
modifications and ALERTS on staged deletions. Detection + alert only:
this daemon never unstages, never modifies the index, never touches
``index.lock``. Unlabeled staged work is parked for Chauncey's ruling —
never auto-resolved (no-silent-double-backtracking law).

Log decision: this daemon CONTINUES the stopgap shell loop's log at
``~/workspace/hidden_files/git-index-watch.log`` so the record is one
unbroken line from the first watch to now. (The shell loop,
``git-index-watch.sh``, is retired separately by the parent agent.)

State: ``~/.levi/daemon/index_watch/state.json`` (fingerprint, baseline
flag, last alerted deletion-set hash). Alerts:
``~/workspace/ddd-inbox/INDEX-WATCH-ALERT-<UTC>.md``.

Supervision: registered in ``levi.perpetual.supervise.SERVICE_ADAPTERS``
as ``levi-index-watch`` (restart_mode="permanent" — restarted if it
dies), and in ``levi.daemon.supervisor`` SERVICE_CATALOG for health
checks. Alive check: ``python -m levi.daemon status index-watch`` or
tail the log; the state file records every tick's timestamp.

stdlib-only.

---------------------------------------------------------------------------
invariants (law -> guard -> prove; tests in tests/test_daemon_index_watch.py)

1. READ-ONLY REPO — the module never writes to the git index. Only the
   allowlisted read-only subcommands (diff, status, rev-parse, ls-files)
   may be invoked; anything else is refused by _git(). (Guard: the
   allowlist + refusal. Prove: static source scan for index-mutating
   subcommand tokens.)
2. ALERT, NEVER RESOLVE — staged deletions produce a timestamped alert
   file in the inbox; the daemon contains no unstage/reset path.
   (Guard: no such code exists. Prove: static scan + alert-content test
   asserting the alert names the paths "parked awaiting Chauncey's
   ruling".)
3. BASELINE, DON'T RE-ALARM — staged deletions already present at first
   run are baselined silently (logged, no alert); alerts fire only when
   the deletion SET changes. (Guard: baselined flag + deletion-set hash
   in state. Prove: two ticks over the same fixture set -> one alert.)
4. NEVER CRASH — every tick section is guarded; a missing repo, broken
   git, or dead ps ends the tick with a note, not an exception.
   (Guard: per-section try/except. Prove: tick against a nonexistent
   repo returns a completed result with a note.)
5. HONEST RECORD — the log records exactly what was observed:
   timestamp, lock presence, process snapshot, staged lists. Nothing is
   inferred about WHO staged what (the shared index doesn't record it).
   (Guard: fields are observations only. Prove: fixture tick -> log
   lines contain the observed values verbatim.)
---------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_POLL_SEC = 5.0
STATE_DIRNAME = "index_watch"

# The ONLY git subcommands this daemon may ever invoke. Everything else
# is refused by _git(). All four are read-only against the index.
READ_ONLY_GIT = frozenset({"diff", "status", "rev-parse", "ls-files"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_repo() -> Path:
    return Path.home() / "workspace" / "levi"


def _default_log() -> Path:
    return Path.home() / "workspace" / "hidden_files" / "git-index-watch.log"


def _default_inbox() -> Path:
    return Path.home() / "workspace" / "ddd-inbox"


def _default_state_dir(home: Optional[Path] = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / ".levi" / "daemon" / STATE_DIRNAME


@dataclass
class IndexWatchConfig:
    repo: Path = field(default_factory=_default_repo)
    log_path: Path = field(default_factory=_default_log)
    inbox_dir: Path = field(default_factory=_default_inbox)
    state_dir: Optional[Path] = None  # None -> ~/.levi/daemon/index_watch
    poll_sec: float = DEFAULT_POLL_SEC
    # Injected for hermetic tests:
    home: Optional[Path] = None
    process_lister: Optional[Callable[[], List[str]]] = None
    now: Optional[Callable[[], str]] = None

    @property
    def index_path(self) -> Path:
        return self.repo / ".git" / "index"

    @property
    def lock_path(self) -> Path:
        return self.repo / ".git" / "index.lock"

    def resolved_state_dir(self) -> Path:
        if self.state_dir is not None:
            return self.state_dir
        return _default_state_dir(self.home)


@dataclass
class IndexEvent:
    ts: str
    mtime: Optional[int]
    sha256: Optional[str]
    lock_present: bool
    git_processes: List[str]
    staged_all: List[str]
    staged_deletions: List[str]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "mtime": self.mtime,
            "sha256": self.sha256,
            "lock_present": self.lock_present,
            "git_processes": self.git_processes,
            "staged_all": self.staged_all,
            "staged_deletions": self.staged_deletions,
            "notes": self.notes,
        }


class IndexWatch:
    """Supervised continuous watch on the shared git index."""

    def __init__(self, config: Optional[IndexWatchConfig] = None) -> None:
        self.config = config or IndexWatchConfig()
        self._stop = threading.Event()

    # -- state ---------------------------------------------------------

    def _state_file(self) -> Path:
        return self.config.resolved_state_dir() / "state.json"

    def _load_state(self) -> Dict[str, Any]:
        try:
            raw = self._state_file().read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        d = self.config.resolved_state_dir()
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, self._state_file())

    # -- observation (read-only) ----------------------------------------

    def _fingerprint(
        self,
    ) -> Tuple[Optional[int], Optional[str], Optional[str], List[str]]:
        """(mtime, sha256, head_sha) of the index+HEAD, or Nones with notes.

        HEAD is fingerprinted too: two different staged-deletion sets can
        leave byte-identical (e.g. empty) index files, distinguishable only
        against HEAD.
        """
        notes: List[str] = []
        idx = self.config.index_path
        try:
            st = idx.stat()
            mtime = int(st.st_mtime)
        except OSError:
            return None, None, None, [f"index not readable: {idx}"]
        try:
            digest = hashlib.sha256(idx.read_bytes()).hexdigest()
        except OSError as exc:
            return mtime, None, None, [f"index hash failed: {exc}"]
        try:
            head_sha = self._git("rev-parse", "HEAD")[0]
        except (OSError, RuntimeError, ValueError, IndexError) as exc:
            head_sha = None
            notes.append(f"HEAD unreadable (unborn?): {exc}")
        return mtime, digest, head_sha, notes

    def _git(self, *args: str, timeout: int = 15) -> List[str]:
        """Run an allowlisted read-only git subcommand. Refuses the rest."""
        if not args or args[0] not in READ_ONLY_GIT:
            raise ValueError(
                f"index-watch: refusing non-read-only git subcommand: {args!r}"
            )
        proc = subprocess.run(
            ["git", "-C", str(self.config.repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}"
            )
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]

    def _staged_lists(self) -> Tuple[List[str], List[str], List[str]]:
        notes: List[str] = []
        try:
            staged_all = self._git("diff", "--cached", "--name-only")
        except (OSError, RuntimeError, ValueError) as exc:
            return [], [], [f"staged list unreadable: {exc}"]
        try:
            staged_del = self._git("diff", "--cached", "--name-only", "--diff-filter=D")
        except (OSError, RuntimeError, ValueError) as exc:
            notes.append(f"deletion list unreadable: {exc}")
            staged_del = []
        return staged_all, staged_del, notes

    def _process_snapshot(self) -> List[str]:
        if self.config.process_lister is not None:
            try:
                return self.config.process_lister()
            except Exception as exc:  # noqa: BLE001 — never crash the tick
                return [f"process lister failed: {exc}"]
        try:
            proc = subprocess.run(
                ["ps", "-eo", "pid,lstart,cmd"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return [f"ps failed: {exc}"]
        out = []
        for line in proc.stdout.splitlines():
            if " git " in f" {line} " and "ps -eo" not in line:
                out.append(line.strip()[:200])
        return out[:20]

    # -- recording -------------------------------------------------------

    def _append_log(self, lines: List[str]) -> None:
        lp = self.config.log_path
        lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as fh:
            for ln in lines:
                fh.write(ln + "\n")

    def _deletions_hash(self, deletions: List[str]) -> str:
        return hashlib.sha256("\n".join(sorted(deletions)).encode()).hexdigest()

    def _write_alert(self, event: IndexEvent) -> Path:
        """Write a timestamped alert file. Detection + alert ONLY."""
        inbox = self.config.inbox_dir
        inbox.mkdir(parents=True, exist_ok=True)
        stamp = _utc_stamp()
        path = inbox / f"INDEX-WATCH-ALERT-{stamp}.md"
        n = 1
        while path.exists():
            n += 1
            path = inbox / f"INDEX-WATCH-ALERT-{stamp}-{n}.md"
        lines = [
            f"# INDEX WATCH ALERT — {event.ts}",
            "",
            "Chauncey — the index watch detected STAGED DELETIONS in the",
            "shared repo index. These are PARKED awaiting your ruling.",
            "Nothing was unstaged or resolved automatically.",
            "",
            f"## Staged deletions ({len(event.staged_deletions)})",
            "",
        ]
        lines += [f"- `{p}`" for p in sorted(event.staged_deletions)]
        lines += [
            "",
            f"## Index lock present at detection: {'YES (someone mid-commit)' if event.lock_present else 'no'}",
            "",
            "## Git processes at detection time",
            "",
        ]
        lines += [f"- `{p}`" for p in event.git_processes] or ["- (none observed)"]
        lines += [
            "",
            f"## Full staged list ({len(event.staged_all)})",
            "",
        ]
        lines += [f"- `{p}`" for p in sorted(event.staged_all)[:100]]
        if len(event.staged_all) > 100:
            lines.append(f"- … and {len(event.staged_all) - 100} more (see watch log)")
        lines += [
            "",
            "---",
            "_Rule: unlabeled staged work is never auto-resolved",
            "(no-silent-double-backtracking). Worktree files intact; only the",
            "ruling moves to you._",
            "",
            f"Watch log: `{self.config.log_path}`",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- tick ------------------------------------------------------------

    def tick(self, now: Optional[str] = None) -> Dict[str, Any]:
        """One watch tick. Never raises; returns a result dict."""
        ts = now or (self.config.now() if self.config.now else None) or _utc_now_iso()
        result: Dict[str, Any] = {
            "ts": ts,
            "changed": False,
            "alert_written": None,
            "baselined": False,
            "notes": [],
        }
        try:
            state = self._load_state()
            mtime, digest, head_sha, notes = self._fingerprint()
            result["notes"].extend(notes)
            prev = (state.get("mtime"), state.get("sha256"), state.get("head_sha"))
            cur = (mtime, digest, head_sha)
            if prev == cur and state.get("baselined"):
                # No change: record the tick heartbeat, nothing else.
                state["last_tick"] = ts
                self._save_state(state)
                return result
            if mtime is None:
                state["last_tick"] = ts
                state["last_error"] = "; ".join(notes) or "index unreadable"
                self._save_state(state)
                return result

            result["changed"] = True
            lock_present = self.config.lock_path.exists()
            staged_all, staged_del, snotes = self._staged_lists()
            result["notes"].extend(snotes)
            event = IndexEvent(
                ts=ts,
                mtime=mtime,
                sha256=digest,
                lock_present=lock_present,
                git_processes=self._process_snapshot(),
                staged_all=staged_all,
                staged_deletions=staged_del,
                notes=list(result["notes"]),
            )
            self._append_log(self._format_event(event))

            if not state.get("baselined"):
                # First run: baseline whatever is already staged. The
                # pre-existing set is the parent's known parked item, not
                # a new appearance — log it, do not alert.
                state["baselined"] = True
                state["baseline_ts"] = ts
                result["baselined"] = True
                result["notes"].append(
                    f"baselined {len(staged_del)} pre-existing staged deletions; no alert"
                )
            elif staged_del:
                dh = self._deletions_hash(staged_del)
                if dh != state.get("last_alert_deletions_hash"):
                    alert_path = self._write_alert(event)
                    state["last_alert_deletions_hash"] = dh
                    state["last_alert_ts"] = ts
                    state["last_alert_path"] = str(alert_path)
                    result["alert_written"] = str(alert_path)

            state["mtime"] = mtime
            state["sha256"] = digest
            state["head_sha"] = head_sha
            state["last_tick"] = ts
            state.pop("last_error", None)
            self._save_state(state)
        except Exception as exc:  # noqa: BLE001 — law 4: never crash
            result["notes"].append(f"tick failed safely: {exc}")
            try:
                self._append_log([f"--- index-watch tick error {ts}: {exc}"])
            except OSError:
                pass
        return result

    def _format_event(self, event: IndexEvent) -> List[str]:
        lines = [
            f"--- index changed {event.ts} "
            f"(sha256 {event.sha256[:12] if event.sha256 else 'none'}) ---"
        ]
        if event.lock_present:
            lines.append("## NOTE: index.lock PRESENT (someone mid-commit)")
        lines.append("## git processes:")
        lines += event.git_processes or ["(none observed)"]
        lines.append(f"## staged deletions ({len(event.staged_deletions)}):")
        lines += event.staged_deletions[:60] or ["(none)"]
        lines.append(f"## staged (all, {len(event.staged_all)}):")
        lines += event.staged_all[:60] or ["(none)"]
        for note in event.notes:
            lines.append(f"## note: {note}")
        return lines

    # -- continuous run ----------------------------------------------------

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> int:
        """Tick until stopped. Returns the number of changes observed."""
        total = 0
        while not self._stop.is_set():
            try:
                if self.tick().get("changed"):
                    total += 1
            except Exception:  # noqa: BLE001, S110 — supervisor restarts us
                pass
        return total


# ---------------------------------------------------------------------------
# supervisor / perpetual wiring


def run_index_watch(
    home: Optional[Path] = None,
    force: bool = False,  # noqa: ARG001 — reserved for cadence callers
) -> Dict[str, Any]:
    """One supervised tick + status summary for health checks."""
    watch = IndexWatch(IndexWatchConfig(home=home))
    tick_result = watch.tick()
    state = watch._load_state()
    return {
        "tick": tick_result,
        "last_tick": state.get("last_tick"),
        "baselined": bool(state.get("baselined")),
        "last_alert_ts": state.get("last_alert_ts"),
        "last_alert_path": state.get("last_alert_path"),
    }


def _status_detail(state: Dict[str, Any]) -> Tuple[bool, str]:
    last = state.get("last_tick")
    if not last:
        return (
            True,
            "index-watch not yet run (start: python -m levi.daemon.index_watch --run)",
        )
    detail = f"index-watch alive, last tick {last}"
    if state.get("last_alert_ts"):
        detail += f"; last alert {state['last_alert_ts']}"
    return True, detail


def _check_index_watch(home: Optional[Path] = None) -> Tuple[bool, str]:
    """Health check for daemon/supervisor.py SERVICE_CATALOG."""
    try:
        summary = run_index_watch(home=home)
    except Exception as exc:  # noqa: BLE001
        return False, f"index-watch check failed: {exc}"
    return _status_detail(
        {
            "last_tick": summary.get("last_tick"),
            "last_alert_ts": summary.get("last_alert_ts"),
        }
    )


def _index_watch_loop(
    stop_event: threading.Event, interval_s: float = DEFAULT_POLL_SEC
) -> None:
    """Perpetual-service adapter: restart_mode='permanent' in supervise.py."""
    watch = IndexWatch(IndexWatchConfig(poll_sec=interval_s))
    while not stop_event.is_set():
        try:
            watch.tick()
        except Exception:  # noqa: BLE001, S110 — crash surfaces; supervisor restarts
            pass
        stop_event.wait(interval_s)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="LEVI index-integrity watch daemon")
    ap.add_argument("--run", action="store_true", help="run continuously until stopped")
    ap.add_argument("--once", action="store_true", help="single tick, print result")
    ap.add_argument(
        "--repo", default=None, help="repo to watch (default ~/workspace/levi)"
    )
    ap.add_argument(
        "--interval", type=float, default=DEFAULT_POLL_SEC, help="poll seconds"
    )
    args = ap.parse_args(argv)

    cfg = IndexWatchConfig(poll_sec=args.interval)
    if args.repo:
        cfg.repo = Path(args.repo).expanduser()
    watch = IndexWatch(cfg)

    if args.once:
        print(json.dumps(watch.tick(), indent=2, default=str))
        return 0
    if args.run:
        try:
            return watch.run()
        except KeyboardInterrupt:
            return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
