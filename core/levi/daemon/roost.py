"""Roost daemon — the perch LEVI's long-running host rests on.

A small stdlib health tick for a LEVI host: it snapshots local pressure
points — the ``/tmp`` volume (the sandbox runs it as a tiny tmpfs that
fills up and kills builds), LEVI's own home directory, and stale
scratch — and writes an honest, atomic snapshot to
``~/.levi/roost/snapshot.json``. A companion ``prune`` clears only the
roost scratch directory, dry-run by default.

Usage::

    from levi.daemon import roost

    snapshot = roost.tick()                       # snapshot health now
    cleared = roost.prune(max_age_days=7)          # dry run: list only
    cleared = roost.prune(max_age_days=7, dry_run=False)

Laws
----
- honest snapshot: a read that fails is recorded as an ``"error"``
  field, never silently dropped and never zero-filled.
- atomic writes: the snapshot lands via temp-file + ``os.replace``;
  a crash mid-write never leaves a half-file.
- prune is caged: it only ever touches files under
  ``<levi_home>/roost/tmp``. Anything outside that directory is
  refused, never deleted.
- dry by default: ``prune`` lists candidates unless ``dry_run=False``
  is passed explicitly.

Deny-closed paths
-----------------
- ``home`` must be a directory (created if missing); a non-directory
  ``home`` is refused.
- ``max_age_days`` must be ``>= 0``; negative ages are refused.
- prune resolves every candidate and requires it to sit inside the
  scratch dir — symlinks escaping the cage are refused per file.

CLI: ``python3 -m levi.daemon.roost tick`` / ``... prune --days 7 --go``

``MANIFEST_ENTRY`` documents the interop-manifest merge for the
``daemon-roost`` capability block; merging it is mechanical.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

MANIFEST_ENTRY = {
    "daemon-roost": {
        "provides": [
            "daemon.roost.tick",
            "daemon.roost.prune",
            "daemon.roost.cmd_roost",
        ],
        "requires": [],
        "description": "Roost daemon — local host health snapshots + scratch pruning",
    }
}

_SCRATCH = Path("roost") / "tmp"
_SNAPSHOT = Path("roost") / "snapshot.json"
_TMP_WARN_PCT = 80.0
_TMP_CRIT_PCT = 95.0


def _home_dir(home: Any = None) -> Path:
    if home is None:
        home = os.environ.get("LEVI_HOME", str(Path.home() / ".levi"))
    base = Path(os.path.expanduser(str(home)))
    if base.exists() and not base.is_dir():
        raise ValueError(f"roost: home is not a directory: {base}")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _band(used_pct: float) -> str:
    if used_pct >= _TMP_CRIT_PCT:
        return "crit"
    if used_pct >= _TMP_WARN_PCT:
        return "warn"
    return "ok"


def _volume(path: str) -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"path": path, "error": str(exc)}
    total = usage.total or 1
    used_pct = 100.0 * usage.used / total
    return {
        "path": path,
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "used_pct": round(used_pct, 2),
        "band": _band(used_pct),
    }


def _stale_scratch(home: Path, max_age_days: float) -> List[Path]:
    scratch = home / _SCRATCH
    if not scratch.is_dir():
        return []
    cutoff = time.time() - max_age_days * 86400
    stale: List[Path] = []
    for entry in scratch.rglob("*"):
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                stale.append(entry)
        except OSError:
            continue
    return sorted(stale)


def _write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), delete=False, encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, indent=2)
        tmp_name = handle.name
    os.replace(tmp_name, path)


def tick(home: Any = None) -> Dict[str, Any]:
    """Snapshot host health now; returns the snapshot dict."""
    base = _home_dir(home)
    snapshot: Dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tmp": _volume(tempfile.gettempdir()),
        "levi_home": _volume(str(base)),
    }
    stale = _stale_scratch(base, 7)
    snapshot["stale_scratch_files"] = len(stale)
    _write_atomic(base / _SNAPSHOT, snapshot)
    snapshot["snapshot"] = str(base / _SNAPSHOT)
    return snapshot


def prune(
    home: Any = None,
    max_age_days: Any = 7,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Clear stale files under <home>/roost/tmp (dry run unless told)."""
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, (int, float)):
        raise ValueError("roost: max_age_days must be a number")
    if max_age_days < 0:
        raise ValueError("roost: max_age_days must be >= 0")
    base = _home_dir(home)
    scratch = base / _SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)

    candidates = _stale_scratch(base, float(max_age_days))
    removed: List[str] = []
    refused: List[str] = []
    for entry in candidates:
        try:
            resolved = entry.resolve()
        except OSError:
            refused.append(str(entry))
            continue
        try:
            resolved.relative_to(scratch.resolve())
        except ValueError:
            refused.append(str(entry))
            continue
        if not dry_run:
            try:
                resolved.unlink()
            except OSError as exc:
                refused.append(f"{entry}: {exc}")
                continue
        removed.append(str(entry))

    return {
        "dry_run": bool(dry_run),
        "scratch": str(scratch),
        "candidates": len(candidates),
        "removed": removed,
        "refused": refused,
    }


def cmd_roost(argv: Optional[List[str]] = None) -> int:
    """CLI entry: ``python3 -m levi.daemon.roost tick``."""
    parser = argparse.ArgumentParser(
        prog="levi.daemon.roost",
        description="Roost: snapshot host health, prune scratch.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("tick", help="write a health snapshot now")
    prune_p = sub.add_parser("prune", help="prune stale roost scratch files")
    prune_p.add_argument("--days", type=float, default=7.0)
    prune_p.add_argument(
        "--go", action="store_true", help="actually delete (default: dry run)"
    )
    args = parser.parse_args(argv)
    try:
        if args.action == "tick":
            result = tick()
        else:
            result = prune(max_age_days=args.days, dry_run=not args.go)
    except (ValueError, OSError) as exc:
        print(f"roost: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def main() -> None:
    sys.exit(cmd_roost())


if __name__ == "__main__":
    main()
