"""Thin, honest subprocess wrapper around the local ``git`` binary.

Forge delegates ALL pack-protocol and repository semantics to the stock
git binary. This module is just the plumbing: find the binary, run it,
surface errors as data.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """A git subprocess failed. ``rc``, ``args``, ``stderr`` are attached."""


_git_path: "str | None | bool" = None  # cached; None = not looked up yet


def git_binary() -> str:
    """Path to the git binary. Raises GitError if git is not installed."""
    global _git_path
    if _git_path is None:
        _git_path = shutil.which("git")
    if not _git_path:
        raise GitError(
            "the 'git' binary was not found on PATH. "
            "LEVI Forge shells out to stock git for all repository work; "
            "install git and try again."
        )
    return _git_path


def git_available() -> bool:
    try:
        git_binary()
        return True
    except GitError:
        return False


def run_git(
    args,
    cwd: "str | Path | None" = None,
    input: "bytes | None" = None,
    env: "dict | None" = None,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run ``git <args>``; return CompletedProcess or raise GitError."""
    cmd = [git_binary()] + [str(a) for a in args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            input=input,
            env=env,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise GitError("git binary disappeared at exec time")
    if check and proc.returncode != 0:
        raise GitError(
            "git %s failed (rc=%d): %s"
            % (" ".join(str(a) for a in args), proc.returncode,
               proc.stderr.decode("utf-8", "replace").strip()[:2000])
        )
    return proc


def git_version() -> str:
    return run_git(["--version"]).stdout.decode("utf-8", "replace").strip()
