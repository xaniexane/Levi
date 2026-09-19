"""LEVI Dream Engine — offline-first dream synthesis and variation.

The dream simulator kernel: recent history goes in as seed, forward
projections come out variated many ways. Failure branches are marked for
compost (REIM), the survivors compress into heritable lessons (RIEM).

Concept adapted from the Levi 30.x lineage (DreamEngine / ImaginationDaemon);
this implementation is original, stdlib-only, and offline-first. Rule-based
synthesis always works; a model provider callable may be injected for
model-assisted dreams, and the engine honestly reports which mode ran.

Nothing here executes actions or touches the network. Dreams are records.
"""

from levi.dream.cycle import run_cycle, run_nightly
from levi.dream.engine import DreamEngine, DreamRecord, synthesize_dream
from levi.dream.journal import (
    DreamJournal,
    default_journal_path,
    enforce_owner_only,
    owner_only_ok,
)
from levi.dream.vary import VARIATIONS, variate

__all__ = [
    "DreamEngine",
    "DreamRecord",
    "DreamJournal",
    "default_journal_path",
    "enforce_owner_only",
    "owner_only_ok",
    "VARIATIONS",
    "synthesize_dream",
    "variate",
    "run_cycle",
    "run_nightly",
]
