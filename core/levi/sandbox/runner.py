"""Command execution inside the selected sandbox backend.

Original LEVI work. stdlib-only.

``build_argv`` constructs the exact wrapper command for a backend; ``run_command``
executes it with stdio inherited (streaming, like a terminal) and returns a
:class:`SandboxResult` describing what happened. No output is captured —
sandbox runs are interactive-friendly.

The subprocess backend NEVER runs without ``allow_degraded=True``: the CLI
sets that only when the user passes ``--i-understand``, after printing the
LOUD warning. Library callers get the same protection by default.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from .backends import BackendSpec, select_backend


@dataclass
class SandboxResult:
    """Outcome of one sandboxed command run."""

    backend: str
    isolation_level: str
    argv: List[str]  # the exact wrapper command executed
    user_cmd: List[str]  # the command the user asked to run
    returncode: int
    degraded_acknowledged: bool = False
    notes: List[str] = field(default_factory=list)


def _repo_root() -> Path:
    # core/levi/sandbox/runner.py -> core/levi -> repo root is two levels up
    # from the *package* dir... actually core/ is the repo's python root, so
    # the checkout root is parents[2] of this file.
    return Path(__file__).resolve().parents[3]


def build_argv(
    spec: BackendSpec,
    user_cmd: Sequence[str],
    *,
    net: bool = False,
    repo: Optional[Path] = None,
    extra_home: Optional[Path] = None,
) -> List[str]:
    """Build the wrapper argv for ``spec`` around ``user_cmd`` (no execution)."""
    user_cmd = list(user_cmd)
    if not user_cmd:
        raise ValueError("no command given to run in the sandbox")

    if spec.name == "bubblewrap":
        home = str(extra_home or os.path.expanduser("~"))
        argv: List[str] = [
            "bwrap",
            "--die-with-parent",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]
        if not net:
            # No network by default: an empty network namespace. With --net we
            # simply omit this flag and share the host network (documented).
            argv.append("--unshare-net")
        argv += [
            "--ro-bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--tmpfs",
            home,  # private empty HOME; host dotfiles stay outside
            "--setenv",
            "HOME",
            home,
        ]
        repo = repo or _repo_root()
        argv += ["--chdir", str(repo), "--"]
        argv += user_cmd
        return argv

    if spec.name == "unshare":
        # Minimal: user + mount namespaces, root-mapped. Filesystem and
        # network are NOT isolated — see the backend spec's limitations.
        return ["unshare", "-Ur", "--"] + user_cmd

    if spec.name == "subprocess":
        return user_cmd

    raise ValueError(f"unknown sandbox backend: {spec.name!r}")


def run_command(
    user_cmd: Sequence[str],
    *,
    backend: Optional[str] = None,
    net: bool = False,
    repo: Optional[Path] = None,
    allow_degraded: bool = False,
) -> SandboxResult:
    """Run ``user_cmd`` in the selected backend, stdio inherited.

    Raises PermissionError if the fallback subprocess backend was selected
    without ``allow_degraded=True`` (the CLI wires this to --i-understand).
    """
    spec = select_backend(backend)
    notes: List[str] = []

    if spec.name == "subprocess" and not allow_degraded:
        raise PermissionError(
            "the only available backend is plain subprocess (NO isolation). "
            "Re-run with --i-understand to acknowledge the degraded sandbox."
        )

    if spec.name == "unshare":
        # Fresh HOME dir for the run; the filesystem is still shared, but at
        # least the sandbox does not inherit (or pollute) the real HOME.
        tmp_home = tempfile.mkdtemp(prefix="levi-sandbox-home-")
        env = dict(os.environ, HOME=tmp_home)
        notes.append(f"fresh HOME dir for this run: {tmp_home}")
    else:
        env = None
        tmp_home = None

    argv = build_argv(spec, user_cmd, net=net, repo=repo)
    try:
        proc = subprocess.run(argv, env=env)
        rc = proc.returncode
    finally:
        if tmp_home:
            # Best-effort cleanup; the dir is empty by construction.
            try:
                os.rmdir(tmp_home)
            except OSError:
                notes.append(f"could not remove temp HOME {tmp_home}; left in place")

    return SandboxResult(
        backend=spec.name,
        isolation_level=spec.isolation_level,
        argv=argv,
        user_cmd=list(user_cmd),
        returncode=rc,
        degraded_acknowledged=allow_degraded,
        notes=notes,
    )
