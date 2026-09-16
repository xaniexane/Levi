"""Forge home resolution and repo-name validation.

``forge_home()`` is deliberately resolved LAZILY at call time (never at
import time) so tests can point it at a tmp dir either by passing
``home=...`` explicitly or by monkeypatching the ``LEVI_FORGE_HOME``
environment variable (or ``HOME`` itself, which :func:`pathlib.Path.home`
reads on every call).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Repo names must be safe path components and safe git ref context.
# (No traversal, no shell metacharacters, bounded length.)
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def forge_home(home: "str | Path | None" = None) -> Path:
    """Return the forge home dir. Never touches the real ~/.levi in tests."""
    if home is not None:
        return Path(home).expanduser()
    env = os.environ.get("LEVI_FORGE_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".levi" / "forge"


def validate_name(name: str) -> str:
    """Normalize and validate a repo name. Raises ValueError on junk.

    A trailing ``.git`` suffix is stripped for display consistency
    (``foo.git`` and ``foo`` are the same repo).
    """
    name = (name or "").strip()
    if name.endswith(".git"):
        name = name[: -len(".git")]
    if not _NAME_RE.match(name):
        raise ValueError(
            "invalid repo name %r: use letters, digits, '.', '_' or '-', "
            "start with a letter or digit, max 100 chars" % name
        )
    return name


def ensure_home(home: "str | Path | None" = None) -> Path:
    """Return the forge home, creating it (owner-only) if missing."""
    root = forge_home(home)
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    for sub in ("repos", "issues", "prs", "ci"):
        (root / sub).mkdir(exist_ok=True)
    return root
