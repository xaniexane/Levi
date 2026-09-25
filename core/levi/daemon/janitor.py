"""LEVI daemon janitor — a report-only audit of LEVI's local state footprint.

LEVI keeps its state on the user's own machine (``~/.levi`` and friends),
and on-disk growth is the one resource a local-first organism can quietly
exhaust. The janitor walks the state tree, measures each immediate
subdirectory, and reports which ones are over their byte budget — with the
largest offenders named.

It never deletes, moves, renames, or touches anything: report-only, by
law (nothing is ever thrown away by automation — a human decides). The
report is what a keeper's hand needs to rule.

Usage::

    from levi.daemon.janitor import audit_state, render_text

    report = audit_state()          # defaults to ~/.levi
    print(render_text(report))

    # with explicit budgets (bytes) and a different base:
    report = audit_state("/var/lib/levi", budgets={"journal": 5_000_000})

CLI::

    python -m levi.daemon.janitor [--base DIR] [--json] [--top N]

Exit code is 0 when every directory is within budget, 2 when any is
over — suitable for a cron keeper's eye. Read-only either way.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "JanitorError",
    "DEFAULT_BUDGETS",
    "audit_state",
    "render_text",
    "SHELF",
    "main",
]


class JanitorError(ValueError):
    """Raised when janitor inputs fail validation."""


#: Default per-directory byte budgets, keyed by immediate-subdirectory
#: name of the state base. Directories not listed are reported with
#: ``budget: None`` (measured, never judged).
DEFAULT_BUDGETS: Dict[str, int] = {
    "journal": 10_000_000,  # append-only baby book
    "growth": 20_000_000,  # harvest/reflect/consolidate artifacts
    "pending": 10_000_000,  # hunt + archive ingest queues
    "crashes": 5_000_000,  # supervision crash reports
    "perpetual": 15_000_000,  # perpetual hunt + supervisor state
    "snapshots": 50_000_000,  # state snapshots
    "logs": 20_000_000,  # daemon logs
}

SHELF = {
    "name": "daemon-janitor",
    "summary": (
        "Report-only audit of LEVI's local state footprint: per-directory "
        "sizes against byte budgets, largest offenders named. Never "
        "deletes or moves anything."
    ),
    "items": [
        {
            "id": "daemon.janitor",
            "kind": "command",
            "summary": "Audit state dirs against budgets; exit 2 if any over.",
            "invoke": "python -m levi.daemon.janitor [--base DIR] [--json]",
        },
    ],
}


def _validate_base(base: Any) -> Path:
    if isinstance(base, Path):
        path = base
    elif isinstance(base, str) and base.strip():
        path = Path(base).expanduser()
    else:
        raise JanitorError("janitor: 'base' must be a non-empty path")
    if not path.is_dir():
        raise JanitorError(f"janitor: base is not a directory: {path}")
    return path


def _validate_budgets(budgets: Any) -> Dict[str, int]:
    if budgets is None:
        return dict(DEFAULT_BUDGETS)
    if not isinstance(budgets, dict):
        raise JanitorError("janitor: 'budgets' must be a dict of name -> bytes")
    cleaned: Dict[str, int] = {}
    for name, value in budgets.items():
        if not isinstance(name, str) or not name.strip():
            raise JanitorError("janitor: budget names must be non-empty str")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise JanitorError(
                f"janitor: budget for {name!r} must be a non-negative int of bytes"
            )
        cleaned[name.strip()] = value
    return cleaned


def _dir_size(path: Path) -> tuple[int, int]:
    """(bytes, file_count) for everything under path. Unreadable files
    are skipped, never fatal — the report says what it measured."""
    total = 0
    files = 0
    for root, _dirs, names in os.walk(path, followlinks=False):
        for name in names:
            try:
                st = os.stat(os.path.join(root, name), follow_symlinks=False)
            except OSError:
                continue
            total += st.st_size
            files += 1
    return total, files


def _top_files(path: Path, n: int) -> List[Dict[str, Any]]:
    sized: List[tuple[int, str]] = []
    for root, _dirs, names in os.walk(path, followlinks=False):
        for name in names:
            full = os.path.join(root, name)
            try:
                size = os.stat(full, follow_symlinks=False).st_size
            except OSError:
                continue
            sized.append((size, os.path.relpath(full, path)))
    sized.sort(key=lambda item: (-item[0], item[1]))
    return [{"path": rel, "bytes": size} for size, rel in sized[:n]]


def audit_state(
    base: Optional[Any] = None,
    budgets: Optional[Dict[str, int]] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """Measure the immediate subdirectories of ``base`` against budgets.

    Returns a report dict. Never writes, deletes, or moves anything.
    ``base`` defaults to ``~/.levi``.
    """
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise JanitorError("janitor: 'top_n' must be a non-negative int")
    base_path = _validate_base(base if base is not None else Path.home() / ".levi")
    budget_map = _validate_budgets(budgets)

    dirs: List[Dict[str, Any]] = []
    total_bytes = 0
    over = 0
    for child in sorted(base_path.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.is_symlink():
            continue
        size, files = _dir_size(child)
        total_bytes += size
        budget = budget_map.get(child.name)
        is_over = budget is not None and size > budget
        if is_over:
            over += 1
        entry: Dict[str, Any] = {
            "name": child.name,
            "bytes": size,
            "files": files,
            "budget": budget,
            "over_budget": is_over,
            "top_files": _top_files(child, top_n) if is_over else [],
        }
        dirs.append(entry)

    return {
        "base": str(base_path),
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "total_bytes": total_bytes,
        "dirs": dirs,
        "over": over,
        "all_within_budget": over == 0,
    }


def _human(n: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}GB"  # pragma: no cover


def render_text(report: Dict[str, Any]) -> str:
    """Render an audit report as plain text for a keeper's eye."""
    lines = [
        f"janitor audit @ {report['ran_at']}",
        f"base: {report['base']}  total: {_human(report['total_bytes'])}",
        "",
    ]
    for entry in report["dirs"]:
        budget = entry["budget"]
        budget_str = _human(budget) if budget is not None else "no budget"
        mark = "OVER " if entry["over_budget"] else "ok   "
        lines.append(
            f"[{mark}] {entry['name']:20s} {_human(entry['bytes']):>10s} "
            f"({entry['files']} files, budget {budget_str})"
        )
        for top in entry["top_files"]:
            lines.append(f"         - {top['path']}  {_human(top['bytes'])}")
    lines.append("")
    if report["all_within_budget"]:
        lines.append("all directories within budget — nothing to rule on.")
    else:
        lines.append(
            f"{report['over']} directorie(s) over budget — report-only; "
            "a human decides what moves."
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: ``python -m levi.daemon.janitor [--base DIR] [--json] [--top N]``."""
    parser = argparse.ArgumentParser(
        prog="python -m levi.daemon.janitor",
        description=(
            "Report-only audit of LEVI's local state footprint. "
            "Never deletes or moves anything. Exit 2 if any directory "
            "is over budget."
        ),
    )
    parser.add_argument(
        "--base",
        default=str(Path.home() / ".levi"),
        help="state base directory (default ~/.levi)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the raw report as JSON"
    )
    parser.add_argument(
        "--top", type=int, default=5, help="largest files named per over-budget dir"
    )
    args = parser.parse_args(argv)

    try:
        report = audit_state(args.base, top_n=args.top)
    except JanitorError as exc:
        print(f"janitor: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))
    return 2 if report["over"] else 0


if __name__ == "__main__":
    sys.exit(main())
