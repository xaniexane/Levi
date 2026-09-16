"""Home resolution for the creed package.

Kept in its own module so ``laws`` / ``masks`` / ``promotion`` can all
import it without circular-import trouble with the package ``__init__``.
"""

from __future__ import annotations

import os
from pathlib import Path


def _levi_home() -> Path:
    """LEVI home, resolved at CALL time (never cached at import).

    Honors ``LEVI_HOME`` first, then ``HOME``; falls back to
    :func:`pathlib.Path.home` for exotic platforms. Tests point
    ``HOME`` at a tmp dir to stay hermetic.
    """
    env = os.environ.get("LEVI_HOME")
    if env and env.strip():
        return Path(env).expanduser()
    home = os.environ.get("HOME")
    if home and home.strip():
        return Path(home)
    return Path.home()
