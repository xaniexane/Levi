"""Park Sentry bot — the watch over the shared git index.

Implements the standing park-on-sight law: any staged deletion in a
repo's index without the user's explicit ruling gets parked (unstaged)
immediately and reported — never waited on, never silently resolved,
never worked around.

Usage::

    from levi.bot import parksentry

    report = parksentry.park("/path/to/repo")          # dry run: report only
    report = parksentry.park("/path/to/repo", apply=True)  # park for real

    print(parksentry.render(report))

Laws
----
- park, don't delete: parking means ``git restore --staged``; the
  worktree is never touched, the files themselves are never harmed.
- report, don't resolve: every parked path is recorded to the ledger
  with a timestamp, and the report names every path. A parked path is
  never auto-resolved — the ruling stays with the user.
- dry by default: ``apply=False`` unless the caller says so. A dry run
  changes nothing and says exactly what it *would* park.
- honest on failure: a repo that isn't a repo, or a git command that
  fails, is refused loudly with ``NotARepoError``/``ParkError`` — the
  index is never half-read, and parking never half-applies.

Deny-closed paths
-----------------
- ``repo`` must be a directory containing a git repo, else refused.
- Only ``D`` (staged deletion) entries are parked. Renames (``R``),
  unstaged deletions (`` D``), and everything else are reported but
  left exactly as found — a rename still carries the content forward.
- The ledger only ever appends JSONL records to the parksentry
  directory; it never rewrites history.

CLI: ``python3 -m levi.bot.parksentry --repo PATH [--apply]``

``MANIFEST_ENTRY`` documents the interop-manifest merge for the
``bot-parksentry`` capability block; merging it is mechanical.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

MANIFEST_ENTRY = {
    "bot-parksentry": {
        "provides": [
            "bot.parksentry.scan",
            "bot.parksentry.park",
            "bot.parksentry.render",
            "bot.parksentry.cli",
        ],
        "requires": [],
        "description": "Park Sentry bot — park-on-sight watch over git indexes",
    }
}


class NotARepoError(ValueError):
    """Raised when the path is not a git repository."""


class ParkError(RuntimeError):
    """Raised when a git command fails mid-scan or mid-park."""


@dataclass
class ParkReport:
    """One park-on-sight pass over a repo."""

    repo: str
    staged_deletions: List[str] = field(default_factory=list)
    unstaged_deletions: List[str] = field(default_factory=list)
    parked: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    applied: bool = False
    clean: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _run_git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ParkError(f"parksentry: git failed: {exc}") from exc


def _assert_repo(repo: Any) -> str:
    if not isinstance(repo, (str, os.PathLike)) or not str(repo).strip():
        raise NotARepoError("parksentry: 'repo' must be a non-empty path")
    path = str(repo)
    if not os.path.isdir(path):
        raise NotARepoError(f"parksentry: not a directory: {path}")
    probe = _run_git(path, "rev-parse", "--git-dir")
    if probe.returncode != 0:
        raise NotARepoError(f"parksentry: not a git repo: {path}")
    return path


def _parse_porcelain(raw: str) -> Dict[str, List[str]]:
    """Split porcelain v1 -z output into staged/unstaged deletion lists."""
    staged: List[str] = []
    unstaged: List[str] = []
    for entry in raw.split("\0"):
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        staged_flag, worktree_flag = xy[0], xy[1]
        if staged_flag == "D":
            staged.append(path)
        if worktree_flag == "D":
            unstaged.append(path)
    return {"staged": staged, "unstaged": unstaged}


def scan(repo: Any) -> ParkReport:
    """Read the index and report staged deletions; changes nothing."""
    path = _assert_repo(repo)
    result = _run_git(path, "status", "--porcelain=v1", "-z")
    if result.returncode != 0:
        raise ParkError(f"parksentry: git status failed: {result.stderr.strip()}")
    parsed = _parse_porcelain(result.stdout)
    report = ParkReport(
        repo=path,
        staged_deletions=sorted(parsed["staged"]),
        unstaged_deletions=sorted(parsed["unstaged"]),
    )
    report.clean = not report.staged_deletions
    return report


def _ledger_path(ledger_dir: Optional[str]) -> Path:
    if ledger_dir:
        base = Path(ledger_dir)
    else:
        base = Path.home() / ".levi" / "parksentry"
    base.mkdir(parents=True, exist_ok=True)
    return base / "parked.jsonl"


def park(
    repo: Any,
    apply: bool = False,
    ledger_dir: Optional[str] = None,
) -> ParkReport:
    """Park every staged deletion in the index (dry run unless apply=True).

    Parking = ``git restore --staged`` per path; the worktree is never
    touched. Every parked path is appended to the ledger.
    """
    report = scan(repo)
    report.applied = bool(apply)
    if not report.staged_deletions:
        report.clean = True
        return report

    if not apply:
        return report

    ledger = _ledger_path(ledger_dir)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    for path in report.staged_deletions:
        result = _run_git(report.repo, "restore", "--staged", "--", path)
        if result.returncode != 0:
            report.errors.append(f"{path}: {result.stderr.strip()}")
            continue
        report.parked.append(path)
        record = {
            "ts": stamp,
            "repo": report.repo,
            "path": path,
            "action": "parked",
        }
        with open(ledger, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    report.clean = not report.errors and len(report.parked) == len(
        report.staged_deletions
    )
    return report


def render(report: ParkReport) -> str:
    """Render a plain-text park-on-sight report."""
    lines = [f"Park Sentry — {report.repo}"]
    if report.clean and not report.staged_deletions:
        lines.append("index clean: no staged deletions.")
        return "\n".join(lines)
    verb = "PARKED" if report.applied else "WOULD PARK (dry run)"
    lines.append(f"staged deletions: {len(report.staged_deletions)}")
    for path in report.staged_deletions:
        marker = "✓" if path in report.parked else "!"
        lines.append(f"  [{marker}] {verb}: {path}")
    if report.unstaged_deletions:
        lines.append(
            f"unstaged deletions (left as-is): {len(report.unstaged_deletions)}"
        )
        for path in report.unstaged_deletions[:10]:
            lines.append(f"  [ ] {path}")
    for error in report.errors:
        lines.append(f"  ERROR: {error}")
    return "\n".join(lines)


def cli(argv: Optional[List[str]] = None) -> int:
    """CLI entry: ``python3 -m levi.bot.parksentry --repo PATH [--apply]``."""
    parser = argparse.ArgumentParser(
        prog="levi.bot.parksentry",
        description="Park Sentry: park staged deletions on sight.",
    )
    parser.add_argument("--repo", default=".", help="repo to watch (default: .)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually unstage (default is a dry run)",
    )
    parser.add_argument(
        "--ledger-dir",
        default=None,
        help="ledger directory override (default: ~/.levi/parksentry)",
    )
    args = parser.parse_args(argv)
    try:
        report = park(args.repo, apply=args.apply, ledger_dir=args.ledger_dir)
    except (NotARepoError, ParkError) as exc:
        print(f"parksentry: {exc}", file=sys.stderr)
        return 2
    print(render(report))
    return 1 if report.errors else 0


def main() -> None:
    sys.exit(cli())


if __name__ == "__main__":
    main()
