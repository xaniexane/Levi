"""Make the uninstalled ``core`` package importable for the test suite.

This lets ``python -m pytest`` run green straight from a fresh clone,
with no install step: the ``levi`` package under ``core/`` is put on
``sys.path`` before any test module imports it. An installed ``levi``
(see ``pip install .``) keeps working too — the tree simply shadows it
during tests, which is the point.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_CORE = str(ROOT / "core")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)
