"""Bridge: sovmail intake calls into mailtriage where capability exists.

- ``MailStore.iter_messages()`` is the intake reader (kept as-is).
- ``TriageEngine.bundle()`` is exposed as the ``bundle_is``
  predicate value so sovmail filters can key on mailtriage's
  baseline bundles (extended, not rewritten).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.mailtriage.store import MailStore
from levi.mailtriage.triage import TriageEngine

__all__ = ["intake", "baseline_bundle"]


def intake(store: MailStore) -> List[Dict[str, Any]]:
    """Read normalized message records from mailtriage's store."""
    return list(store.iter_messages())


def baseline_bundle(rec: Dict[str, Any], triage_home: Optional[Path] = None) -> str:
    """mailtriage's baseline bundle for a record (receipts / newsletters
    / people / notifications / other)."""
    engine = TriageEngine(home=triage_home)
    return engine.bundle(rec)
