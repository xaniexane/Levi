"""LEVI host sandbox — run experimental work in an isolated Linux environment.

Original LEVI work. stdlib-only.

Three backends, best-first, with an honest isolation contract: each backend
reports exactly what it does and does not guarantee, and the CLI prints that
report on every run. The module NEVER claims more isolation than the backend
actually provides.

- ``bubblewrap``  (``bwrap``): user/pid/ipc/uts namespaces, read-only bind of
  the whole tree, private tmpfs HOME, no network unless asked. STRONG.
- ``unshare``     (``unshare -Ur``): user + mount namespace only, fresh HOME
  dir, filesystem still visible and writable, no network isolation. BASIC.
- ``subprocess``  (plain): no isolation at all. The CLI prints a LOUD warning
  and requires ``--i-understand`` acknowledgement. NONE (degraded).

This is unrelated to ``levi.surgeon.sandbox`` (the Stage-1 propose/HITL gate,
which inspects text and never executes anything). This module EXECUTES
commands — prefer the strongest backend the host actually has.
"""

from __future__ import annotations

from .backends import (
    BackendSpec,
    describe_backends,
    isolation_report,
    select_backend,
)
from .runner import SandboxResult, run_command

__all__ = [
    "BackendSpec",
    "SandboxResult",
    "describe_backends",
    "isolation_report",
    "run_command",
    "select_backend",
]
