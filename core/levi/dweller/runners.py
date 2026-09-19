"""Dweller runners — the built-in grind kinds.

Three kinds, all hermetic, all read-only, NO network anywhere in this
module (a network-seeking runner does not exist here; grep will confirm):

- ``repo-sweep`` — count and index Python modules under a root:
  files, modules, lines, per-directory breakdown, largest files.
- ``crossref`` — exhaustive cross-reference of two file sets: every
  identifier token defined in set A is looked up in every file of set
  B. Returns the token -> files mapping plus summary counts.
- ``watch`` — long-horizon monitor: re-checks a zero-argument
  condition up to N times with exponential backoff between attempts,
  stopping early when the condition turns true. The sleep function is
  injectable so tests stay fast.

Every runner takes ``sandbox_root`` and refuses any path outside it —
the Dweller never acts on the world beyond its sandbox. stdlib only.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

#: Kinds the Dweller knows how to grind.
RUNNER_KINDS = ("repo-sweep", "crossref", "watch")


class RunnerError(Exception):
    """A runner refused or failed honestly."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _inside(path: str, sandbox_root: str) -> bool:
    """True when ``path`` resolves inside ``sandbox_root``."""
    root = os.path.realpath(os.path.abspath(sandbox_root))
    target = os.path.realpath(os.path.abspath(path))
    return target == root or target.startswith(root + os.sep)


def _check_paths(paths: List[str], sandbox_root: str) -> None:
    outside = [p for p in paths if not _inside(p, sandbox_root)]
    if outside:
        raise RunnerError(
            "refused: path(s) outside sandbox %r: %s"
            % (sandbox_root, ", ".join(outside))
        )


# ---------------------------------------------------------------------------
# repo-sweep
# ---------------------------------------------------------------------------


def run_repo_sweep(
    root: str, sandbox_root: str, include_tests: bool = True
) -> Dict[str, Any]:
    """Count and index Python modules under ``root``.

    Returns files scanned, module count, total lines, per-directory
    module counts, and the largest files. Read-only.
    """
    _check_paths([root], sandbox_root)
    if not os.path.isdir(root):
        raise RunnerError("repo-sweep: not a directory: %r" % root)
    modules: List[Dict[str, Any]] = []
    total_lines = 0
    per_dir: Dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if not include_tests and (
                fn.startswith("test_")
                or fn.endswith("_test.py")
                or dirpath.rstrip(os.sep).endswith((os.sep + "tests", os.sep + "test"))
            ):
                continue
            full = os.path.join(dirpath, fn)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    lines = sum(1 for _ in fh)
            except OSError as exc:
                raise RunnerError(
                    "repo-sweep: cannot read %r: %s" % (full, exc)
                ) from exc
            rel = os.path.relpath(full, root)
            modules.append({"path": rel, "lines": lines})
            total_lines += lines
            top = rel.split(os.sep)[0] if os.sep in rel else "."
            per_dir[top] = per_dir.get(top, 0) + 1
    largest = sorted(modules, key=lambda m: m["lines"], reverse=True)[:10]
    return {
        "root": os.path.abspath(root),
        "files_scanned": len(modules),
        "total_lines": total_lines,
        "per_dir": dict(sorted(per_dir.items())),
        "largest_files": largest,
        "include_tests": include_tests,
    }


# ---------------------------------------------------------------------------
# crossref
# ---------------------------------------------------------------------------


def _tokens_of_file(path: str) -> set:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return set(_TOKEN_RE.findall(fh.read()))


def run_crossref(
    set_a: List[str], set_b: List[str], sandbox_root: str, min_token_len: int = 3
) -> Dict[str, Any]:
    """Exhaustively cross-reference two file sets.

    Every identifier token in set A is searched for in every file of
    set B. Returns ``token -> [files in B containing it]`` for tokens
    that appear on both sides, plus summary counts. Read-only.
    """
    _check_paths(list(set_a) + list(set_b), sandbox_root)
    for p in list(set_a) + list(set_b):
        if not os.path.isfile(p):
            raise RunnerError("crossref: not a file: %r" % p)
    a_tokens: Dict[str, List[str]] = {}
    for p in set_a:
        for tok in _tokens_of_file(p):
            if len(tok) >= min_token_len:
                a_tokens.setdefault(tok, []).append(p)
    b_index: Dict[str, set] = {}
    for p in set_b:
        b_index[p] = _tokens_of_file(p)
    hits: Dict[str, List[str]] = {}
    for tok in a_tokens:
        found = sorted(p for p, toks in b_index.items() if tok in toks)
        if found:
            hits[tok] = found
    return {
        "set_a_files": len(set_a),
        "set_b_files": len(set_b),
        "tokens_in_a": len(a_tokens),
        "tokens_cross_referenced": len(hits),
        "hits": hits,
    }


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------


def run_watch(
    condition: Callable[[], Any],
    *,
    times: int,
    initial_delay_s: float = 1.0,
    factor: float = 2.0,
    max_delay_s: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Re-check ``condition`` up to ``times`` with exponential backoff.

    Stops early when the condition returns truthy. ``sleep`` is
    injectable (tests monkeypatch it). No network — the condition is a
    local callable supplied by the caller.
    """
    if times < 1:
        raise RunnerError("watch: times must be >= 1")
    attempts: List[Dict[str, Any]] = []
    delay = initial_delay_s
    for n in range(1, times + 1):
        try:
            value = condition()
            error = ""
        except Exception as exc:
            value, error = None, "%s: %s" % (type(exc).__name__, exc)
        satisfied = bool(value) and not error
        attempts.append(
            {
                "attempt": n,
                "satisfied": satisfied,
                "value": value if error == "" and value is not None else None,
                "error": error,
                "ts": _utcnow(),
            }
        )
        if satisfied:
            break
        if n < times:
            sleep(min(delay, max_delay_s))
            delay = min(delay * factor, max_delay_s)
    return {
        "attempts": attempts,
        "attempts_made": len(attempts),
        "satisfied": attempts[-1]["satisfied"],
        "times_requested": times,
    }
