"""Census daemon — the stock-taker.

LEVI keeps packing itself to the brim; the census keeps the honest
count. :func:`take_census` counts the organism's own surfaces — how
many connectors are registered, how many skills, how many modules the
interop manifest declares, how many bot and daemon modules ship on
disk — and :func:`record` appends the dated snapshot to
``~/.levi/daemon/census.jsonl``. :func:`diff_counts` compares two
snapshots surface by surface: what grew, what shrank, what appeared,
what vanished.

Counts are injected as ``providers`` (name → callable returning an
int) so tests never need the real registries; the default providers
read the live ones lazily.

Laws
----
- observe-only: providers may read registries and the tree; the only
  write the census ever makes is its own snapshot log
- honest counts: every count is a real ``len()`` of something that
  exists — never estimated, never rounded into a story
- deny-closed: a provider returning a non-int (or raising) fails the
  census loudly instead of recording a half-count; a corrupt snapshot
  line is skipped on read, never trusted
- skippable: a missed census leaves no record and breaks nothing

Run it: ``python -m levi.daemon.census snapshot`` /
``python -m levi.daemon.census diff``
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "CensusError",
    "take_census",
    "record",
    "latest",
    "history",
    "diff_counts",
    "default_providers",
    "DEFAULT_LOG_PATH",
]

DEFAULT_LOG_PATH = Path.home() / ".levi" / "daemon" / "census.jsonl"


class CensusError(ValueError):
    """A census was refused: bad provider, bad count, bad home."""


def _home() -> Path:
    return Path.home()


def _log_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "daemon" / "census.jsonl"


def _count_package_modules(package: str) -> int:
    """Honest count of ``*.py`` modules shipped in a ``levi.<package>`` dir."""
    import levi

    pkg_dir = Path(levi.__file__).resolve().parent / package
    if not pkg_dir.is_dir():
        raise CensusError(f"census: package dir missing: levi.{package}")
    return sum(
        1 for p in pkg_dir.glob("*.py") if p.name not in ("__init__.py", "__main__.py")
    )


def _count_connectors() -> int:
    from levi.connectors.base import registry

    return len(registry.list())


def _count_skills() -> int:
    from levi.skill.registry import SkillRegistry

    return len(SkillRegistry().list())


def _count_manifest_modules() -> int:
    from levi.interop.manifest import DECLARATIONS

    return len(DECLARATIONS)


def default_providers() -> Dict[str, Callable[[], int]]:
    """The live surface providers: name → thunk returning a real count."""
    return {
        "connectors": _count_connectors,
        "skills": _count_skills,
        "manifest_modules": _count_manifest_modules,
        "bot_modules": lambda: _count_package_modules("bot"),
        "daemon_modules": lambda: _count_package_modules("daemon"),
    }


def _guarded_providers(
    providers: Optional[Dict[str, Callable[[], int]]],
) -> Dict[str, Callable[[], int]]:
    if providers is None:
        return default_providers()
    if not isinstance(providers, dict) or not providers:
        raise CensusError("census: 'providers' must be a non-empty dict")
    for name, fn in providers.items():
        if not isinstance(name, str) or not name.strip():
            raise CensusError("census: provider names must be non-empty strings")
        if not callable(fn):
            raise CensusError(f"census: provider {name!r} is not callable")
    return providers


def take_census(
    *,
    home: Optional[Path] = None,
    providers: Optional[Dict[str, Callable[[], int]]] = None,
    taken_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Count every surface. Any provider failure fails the whole census."""
    _ = home  # take_census itself writes nothing; home is for record()
    prov = _guarded_providers(providers)
    counts: Dict[str, int] = {}
    for name in sorted(prov):
        try:
            value = prov[name]()
        except Exception as exc:
            raise CensusError(f"census: provider {name!r} failed: {exc}") from exc
        if isinstance(value, bool) or not isinstance(value, int):
            raise CensusError(f"census: provider {name!r} returned non-int {value!r}")
        if value < 0:
            raise CensusError(f"census: provider {name!r} returned negative {value}")
        counts[name] = value
    return {
        "taken_at": taken_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": counts,
        "total": sum(counts.values()),
    }


def record(
    *,
    home: Optional[Path] = None,
    providers: Optional[Dict[str, Callable[[], int]]] = None,
) -> Dict[str, Any]:
    """Take a census and append it to the snapshot log. Returns it."""
    snapshot = take_census(home=home, providers=providers)
    path = _log_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return snapshot


def _read_snapshots(home: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _log_file(home)
    if not path.exists():
        return []
    snapshots: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(raw, dict)
            and isinstance(raw.get("counts"), dict)
            and raw.get("taken_at")
        ):
            snapshots.append(raw)
    return snapshots


def latest(*, home: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The most recent snapshot, or None when no census has ever run."""
    snapshots = _read_snapshots(home)
    return snapshots[-1] if snapshots else None


def history(*, home: Optional[Path] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """Past snapshots, newest first. Corrupt lines are skipped."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, limit)
    return list(reversed(_read_snapshots(home)[-limit:]))


def diff_counts(prev: Dict[str, Any], cur: Dict[str, Any]) -> Dict[str, Any]:
    """Surface-by-surface diff between two snapshots.

    Returns ``{"grew": {name: delta}, "shrank": {name: delta},
    "appeared": [names], "vanished": [names], "total_delta": int}``.
    Either side missing honest counts is refused — a diff never
    guesses.
    """
    for label, snap in (("prev", prev), ("cur", cur)):
        if not isinstance(snap, dict) or not isinstance(snap.get("counts"), dict):
            raise CensusError(f"census: {label} snapshot has no honest counts")
    prev_counts = prev["counts"]
    cur_counts = cur["counts"]
    for label, counts in (("prev", prev_counts), ("cur", cur_counts)):
        for name, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise CensusError(f"census: {label} count {name!r} is not an int")
    grew: Dict[str, int] = {}
    shrank: Dict[str, int] = {}
    appeared = sorted(set(cur_counts) - set(prev_counts))
    vanished = sorted(set(prev_counts) - set(cur_counts))
    for name in sorted(set(prev_counts) & set(cur_counts)):
        delta = cur_counts[name] - prev_counts[name]
        if delta > 0:
            grew[name] = delta
        elif delta < 0:
            shrank[name] = -delta
    return {
        "grew": grew,
        "shrank": shrank,
        "appeared": appeared,
        "vanished": vanished,
        "total_delta": int(cur.get("total", 0)) - int(prev.get("total", 0)),
    }


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "daemon-census",
            provides=(
                "daemon.census.take",
                "daemon.census.record",
                "daemon.census.diff",
                "daemon.census.cli",
            ),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.daemon.census", description="LEVI surface census"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot", help="take a census and append the snapshot")
    sub.add_parser("diff", help="diff the last two snapshots")
    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        snap = record()
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        return 0
    snaps = _read_snapshots()
    if len(snaps) < 2:
        print("census: need at least two snapshots to diff")
        return 1
    print(json.dumps(diff_counts(snaps[-2], snaps[-1]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
