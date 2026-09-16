"""Backend selection and honest isolation reporting for ``levi sandbox``.

Original LEVI work. stdlib-only.

The selection order is fixed: bubblewrap -> unshare -> plain subprocess.
Availability is probed with ``shutil.which`` (injectable for tests). A forced
backend that is NOT available raises instead of silently downgrading — silent
downgrade would be a dishonest isolation claim.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# Isolation levels. The contract: a backend's level must describe what the
# flags we actually pass deliver — never the tool's marketing page.
STRONG = "strong"  # namespaces + read-only tree + private HOME + no net
BASIC = "basic"  # user/mount namespace only; fs still visible and writable
NONE = "none"  # plain subprocess; NO isolation


@dataclass
class BackendSpec:
    """One sandbox backend and its honest isolation contract."""

    name: str  # "bubblewrap" | "unshare" | "subprocess"
    binary: str  # executable probed, "" for plain subprocess
    available: bool
    isolation_level: str  # STRONG | BASIC | NONE
    guarantees: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"{self.name}: isolation={self.isolation_level}"


def _specs(which: Callable[[str], Optional[str]]) -> List[BackendSpec]:
    """Build the three backend specs; ``which`` is injectable for tests."""
    bwrap = which("bwrap")
    unshare = which("unshare")
    return [
        BackendSpec(
            name="bubblewrap",
            binary="bwrap",
            available=bwrap is not None,
            isolation_level=STRONG,
            guarantees=[
                "new user, pid, ipc and uts namespaces (uid 0 inside, unprivileged outside)",
                "whole filesystem tree bound read-only; only HOME and /tmp are writable (tmpfs)",
                "private empty HOME per run — no access to your dotfiles or ~/.levi",
                "no network access unless --net is passed",
                "dies with the parent process (--die-with-parent)",
            ],
            limitations=[
                "shares the host kernel — kernel exploits are out of scope",
                "with --net, the sandbox sees your real network (no filtering)",
                "requires unprivileged user namespaces to be enabled in the kernel",
            ],
        ),
        BackendSpec(
            name="unshare",
            binary="unshare",
            available=unshare is not None,
            isolation_level=BASIC,
            guarantees=[
                "new user namespace (root inside, unprivileged outside)",
                "new mount namespace (mount changes stay inside)",
                "fresh empty HOME directory for the run",
            ],
            limitations=[
                "NO filesystem hiding: your files are still visible AND writable",
                "NO network isolation: the sandbox uses your network",
                "NO pid/ipc isolation: host processes are visible",
                "weaker than bubblewrap in every dimension — prefer bwrap when present",
            ],
        ),
        BackendSpec(
            name="subprocess",
            binary="",
            available=True,  # always available; that is the point of the fallback
            isolation_level=NONE,
            guarantees=[
                "none — this is the same process tree, filesystem and network as you",
            ],
            limitations=[
                "NO isolation whatsoever: reads/writes your real files, real HOME, real network",
                "only here so `levi sandbox run` still functions on minimal hosts",
                "the CLI prints a LOUD warning and requires --i-understand to proceed",
            ],
        ),
    ]


def describe_backends(
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> List[BackendSpec]:
    """Return all backend specs in preference order, with live availability."""
    return _specs(which or shutil.which)


def select_backend(
    preferred: Optional[str] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> BackendSpec:
    """Pick the best available backend.

    ``preferred`` may be "auto" (default), "bubblewrap", "unshare" or
    "subprocess". A forced backend that is unavailable raises ValueError —
    we never silently downgrade isolation.
    """
    which = which or shutil.which
    specs = _specs(which)
    by_name = {s.name: s for s in specs}
    if preferred in (None, "auto"):
        for spec in specs:
            if spec.available:
                return spec
        # Unreachable: subprocess is always available.
        raise RuntimeError("no sandbox backend available")
    if preferred not in by_name:
        raise ValueError(
            f"unknown backend {preferred!r}; choose from " + ", ".join(by_name)
        )
    spec = by_name[preferred]
    if not spec.available:
        raise ValueError(
            f"backend {preferred!r} requested but {spec.binary!r} not found on PATH; "
            "not downgrading silently — install it or use --backend auto"
        )
    return spec


def isolation_report(spec: BackendSpec) -> str:
    """One honest paragraph about what ``spec`` actually guarantees."""
    lines = [
        f"backend: {spec.name}  (isolation level: {spec.isolation_level})",
        "guarantees:",
    ]
    lines += [f"  + {g}" for g in spec.guarantees]
    lines.append("limitations:")
    lines += [f"  - {lim}" for lim in spec.limitations]
    return "\n".join(lines)
