"""LEVI teach: turn approved corpora into curriculum-ordered training data.

The teach pipeline converts approved knowledge sources (course corpora,
academy lessons, growth learnings, seed curriculum) into clean training
sequences ordered simple -> complex by the v2 curriculum builder, deduped
via the v2 corpus manager, with versioned manifests.

Standing policy (hard gate): NEWS stays OUT of training weights. Every
converter and every prepared run passes the corpus manager's policy check.

CLI: ``levi teach plan | prepare --out DIR | stats``

This package is data plumbing, not cognition: it verifies that prepared
*training data* represents the taught material (teachback coverage). It
makes no claims about model capability.
"""

from __future__ import annotations

__all__ = [
    "TEACH_VERSION",
    "teach_home",
    "registry_dir",
]

import os
from pathlib import Path

TEACH_VERSION = "0.1.0"


def teach_home() -> Path:
    """``~/.levi/teach`` (override with ``LEVI_HOME``)."""
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "teach"


def registry_dir() -> Path:
    """Where per-run teach manifests accumulate (for ``levi teach stats``)."""
    return teach_home() / "manifests"
