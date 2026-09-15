"""Root pytest suite for the LEVI × L.W.P. Python codebases.

These tests are hermetic: no network, no daemons, no user HOME writes.
They only add ``core/`` and ``delivery/megazord/`` to ``sys.path`` so the
two Python products are importable from a checkout without installing.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for _rel in ("core", "delivery/megazord"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)
