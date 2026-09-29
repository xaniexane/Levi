"""Syncwatch — divergence watchdog for mirrored directory pairs.

Chauncey's machines sync through several clouds at once; the same file
can quietly become two different files. Syncwatch watches configured
directory pairs (left/right mirrors) and reports, per relative path,
whether the two sides still agree.

Read-only by design: it never writes, moves, or merges anything in the
watched trees. When both sides of a file decode as text it asks the
``reunion`` engine for the verdict class (converged / single-line /
reconcilable / conflicted); the verdict is reported, never acted on.
Conflicts stay held for the keeper.

Signals (via the signalbus, transitions only — no floods):

- ``syncwatch.diverged`` — a path newly diverges, or its hashes change
  again. Payload: pair, relpath, both hashes and sizes, reunion verdict.
- ``syncwatch.reunited`` — a previously-diverged path agrees again.

State (last-seen hashes per pair/path) lives owner-only under
``~/.levi/syncwatch/state.json``; pair config under
``~/.levi/syncwatch/pairs.json``. Removing a pair retires it to a
ledger — nothing is ever deleted.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.syncwatch`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.daemon.signalbus import SignalBus

__all__ = [
    "SyncwatchError",
    "SyncwatchReport",
    "Syncwatch",
    "DEFAULT_ROOT",
    "PAIR_NAME_RE",
    "MAX_FILES_PER_SIDE",
    "MAX_FILE_BYTES",
    "MAX_REUNION_CHARS",
]


class SyncwatchError(ValueError):
    """Raised when pair config or the store fails validation."""


#: Pair names: lowercase, short, filesystem-friendly.
PAIR_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

#: Deny-closed scan guards: refuse a side that looks unbounded rather
#: than walking it forever.
MAX_FILES_PER_SIDE = 2000
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB — larger files are skipped, honestly noted
MAX_REUNION_CHARS = 100_000  # text pairs bigger than this skip the reunion verdict

DEFAULT_ROOT = Path.home() / ".levi" / "syncwatch"
_PAIRS_FILE = "pairs.json"
_STATE_FILE = "state.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class SyncwatchReport:
    """What one tick saw. JSON-serializable via :meth:`to_dict`."""

    pairs_checked: int = 0
    diverged: List[Dict[str, Any]] = field(default_factory=list)
    reunited: List[Dict[str, Any]] = field(default_factory=list)
    one_sided: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Syncwatch:
    """Watches left/right directory pairs for divergent copies."""

    def __init__(
        self,
        root: Optional[Path] = None,
        bus: Optional[SignalBus] = None,
    ) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.bus = bus if bus is not None else SignalBus()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    # -- pair config ----------------------------------------------------

    def _pairs_path(self) -> Path:
        return self.root / _PAIRS_FILE

    def _load_store(self) -> Dict[str, Any]:
        path = self._pairs_path()
        if not path.exists():
            return {"pairs": [], "retired": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SyncwatchError(f"syncwatch: pairs store unreadable: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("pairs"), list):
            raise SyncwatchError(
                "syncwatch: pairs store malformed — refused, never defaulted"
            )
        return data

    def _save_store(self, data: Dict[str, Any]) -> None:
        tmp = self._pairs_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self._pairs_path())

    def add_pair(self, name: str, left: str, right: str) -> Dict[str, str]:
        """Register a mirrored pair. Deny-closed: bad config is refused."""
        if not isinstance(name, str) or not PAIR_NAME_RE.match(name):
            raise SyncwatchError(
                "syncwatch: pair name must match ^[a-z][a-z0-9_-]{0,31}$"
            )
        sides = {}
        for label, raw in (("left", left), ("right", right)):
            if not isinstance(raw, str) or not raw:
                raise SyncwatchError(
                    f"syncwatch: pair '{name}' {label} must be a non-empty str"
                )
            path = Path(raw)
            if not path.is_absolute():
                raise SyncwatchError(
                    f"syncwatch: pair '{name}' {label} must be absolute, got {raw!r}"
                )
            if not path.is_dir():
                raise SyncwatchError(
                    f"syncwatch: pair '{name}' {label} is not a directory: {raw}"
                )
            sides[label] = path.resolve()
        if sides["left"] == sides["right"]:
            raise SyncwatchError(
                f"syncwatch: pair '{name}' left and right are the same directory"
            )
        for a, b in (("left", "right"), ("right", "left")):
            try:
                sides[a].relative_to(sides[b])
            except ValueError:
                pass
            else:
                raise SyncwatchError(
                    f"syncwatch: pair '{name}' {a} lives inside {b} — refused"
                )
        store = self._load_store()
        if any(p["name"] == name for p in store["pairs"]):
            raise SyncwatchError(f"syncwatch: pair '{name}' already registered")
        record = {
            "name": name,
            "left": str(sides["left"]),
            "right": str(sides["right"]),
            "added_at": _utcnow().isoformat(),
        }
        store["pairs"].append(record)
        self._save_store(store)
        return record

    def remove_pair(self, name: str, reason: str = "") -> Dict[str, Any]:
        """Retire a pair to the ledger — moved, never deleted."""
        store = self._load_store()
        remaining = [p for p in store["pairs"] if p["name"] != name]
        if len(remaining) == len(store["pairs"]):
            raise SyncwatchError(f"syncwatch: no pair named '{name}'")
        retired = next(p for p in store["pairs"] if p["name"] == name)
        retired = dict(retired)
        retired["removed_at"] = _utcnow().isoformat()
        retired["reason"] = reason
        store["pairs"] = remaining
        store.setdefault("retired", []).append(retired)
        self._save_store(store)
        # Drop its watermark state too — a re-added pair starts fresh.
        state = self._load_state()
        state.pop(name, None)
        self._save_state(state)
        return retired

    def list_pairs(self) -> List[Dict[str, Any]]:
        return sorted(self._load_store()["pairs"], key=lambda p: p["name"])

    # -- watermark state -------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        path = self.root / _STATE_FILE
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        path = self.root / _STATE_FILE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    # -- scanning --------------------------------------------------------

    def _scan_side(
        self, root: Path, report: SyncwatchReport, pair: str, side: str
    ) -> Dict[str, Dict[str, Any]]:
        """relpath -> {size, sha256}. Guarded: file-count cap, size cap."""
        found: Dict[str, Dict[str, Any]] = {}
        count = 0
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in sorted(filenames):
                full = Path(dirpath) / filename
                if not full.is_file() or full.is_symlink():
                    continue
                count += 1
                if count > MAX_FILES_PER_SIDE:
                    raise SyncwatchError(
                        f"syncwatch: pair '{pair}' {side} exceeds "
                        f"{MAX_FILES_PER_SIDE} files — refused, never half-scanned"
                    )
                try:
                    size = full.stat().st_size
                except OSError as exc:
                    report.skipped.append(
                        {
                            "pair": pair,
                            "side": side,
                            "relpath": str(full.relative_to(root)),
                            "why": f"stat failed: {exc}",
                        }
                    )
                    continue
                if size > MAX_FILE_BYTES:
                    report.skipped.append(
                        {
                            "pair": pair,
                            "side": side,
                            "relpath": str(full.relative_to(root)),
                            "why": f"{size} bytes exceeds {MAX_FILE_BYTES} cap",
                        }
                    )
                    continue
                rel = full.relative_to(root).as_posix()
                found[rel] = {"size": size, "sha256": _sha256_file(full), "path": full}
        return found

    def _reunion_verdict(self, left_text: str, right_text: str) -> Optional[str]:
        """Ask the reunion engine to classify a text pair. Honest None on failure."""
        try:
            from levi.engines import reunion as _reunion_mod  # noqa: F401 — ensures registration
            from levi.engines.base import registry

            result = registry.run(
                "reunion",
                {
                    "versions": [
                        {"id": "left", "text": left_text},
                        {"id": "right", "text": right_text},
                    ]
                },
            )
            return str(result.verdict.get("status"))
        except Exception:
            return None

    # -- the tick --------------------------------------------------------

    def tick(self) -> SyncwatchReport:
        report = SyncwatchReport()
        state = self._load_state()
        for pair in self.list_pairs():
            name = pair["name"]
            left_root = Path(pair["left"])
            right_root = Path(pair["right"])
            if not left_root.is_dir() or not right_root.is_dir():
                report.errors.append(
                    f"syncwatch: pair '{name}' side missing "
                    f"(left={left_root.is_dir()}, right={right_root.is_dir()})"
                )
                continue
            report.pairs_checked += 1
            try:
                left = self._scan_side(left_root, report, name, "left")
                right = self._scan_side(right_root, report, name, "right")
            except SyncwatchError as exc:
                report.errors.append(str(exc))
                continue
            pair_state = state.setdefault(name, {})
            for relpath in sorted(set(left) | set(right)):
                linfo, rinfo = left.get(relpath), right.get(relpath)
                if linfo is None or rinfo is None:
                    report.one_sided.append(
                        {
                            "pair": name,
                            "relpath": relpath,
                            "side": "left" if linfo else "right",
                        }
                    )
                    continue
                if linfo["sha256"] == rinfo["sha256"]:
                    if relpath in pair_state:
                        report.reunited.append({"pair": name, "relpath": relpath})
                        self.bus.publish(
                            "syncwatch.reunited",
                            {"pair": name, "relpath": relpath},
                            publisher="syncwatch",
                        )
                        del pair_state[relpath]
                    continue
                # Divergent bytes.
                reunion_status: Optional[str] = None
                left_text = right_text = None
                try:
                    left_text = linfo["path"].read_text(encoding="utf-8")
                    right_text = rinfo["path"].read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    left_text = right_text = None
                if (
                    left_text is not None
                    and right_text is not None
                    and len(left_text) + len(right_text) <= MAX_REUNION_CHARS
                ):
                    reunion_status = self._reunion_verdict(left_text, right_text)
                record = {
                    "pair": name,
                    "relpath": relpath,
                    "left_sha256": linfo["sha256"],
                    "right_sha256": rinfo["sha256"],
                    "left_size": linfo["size"],
                    "right_size": rinfo["size"],
                    "reunion": reunion_status,
                }
                report.diverged.append(record)
                prev = pair_state.get(relpath)
                if (
                    prev is None
                    or prev.get("left_sha256") != linfo["sha256"]
                    or prev.get("right_sha256") != rinfo["sha256"]
                ):
                    self.bus.publish(
                        "syncwatch.diverged", record, publisher="syncwatch"
                    )
                pair_state[relpath] = {
                    "left_sha256": linfo["sha256"],
                    "right_sha256": rinfo["sha256"],
                    "reunion": reunion_status,
                    "at": _utcnow().isoformat(),
                }
        self._save_state(state)
        return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m levi.daemon.syncwatch")
    ap.add_argument(
        "--root",
        default=None,
        help="State root (default ~/.levi/syncwatch).",
    )
    args = ap.parse_args(argv)
    watcher = Syncwatch(root=Path(args.root) if args.root else None)
    report = watcher.tick()
    print(
        "syncwatch tick: pairs=%d diverged=%d reunited=%d one-sided=%d skipped=%d errors=%d"
        % (
            report.pairs_checked,
            len(report.diverged),
            len(report.reunited),
            len(report.one_sided),
            len(report.skipped),
            len(report.errors),
        )
    )
    for d in report.diverged:
        print("  diverged: %s/%s reunion=%s" % (d["pair"], d["relpath"], d["reunion"]))
    for r in report.reunited:
        print("  reunited: %s/%s" % (r["pair"], r["relpath"]))
    for err in report.errors:
        print(f"  error:    {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
