"""SOXI teaching return loop.

Inbox -> verify -> refine -> promote -> sync-package.

"Then the answers come back here and are verified and refined and
put in cloud — and anyone that connects to cloud updates the
collective intelligence." (Chauncey, 2026-09-22)
"""

from .common import SUBJECTS, FRAMES, KINDS, base_dir
from .inbox import intake, ready_batches
from .verify import verify_batch
from .refine import refine_batch
from .promote import promote_batch, revert_promotion, store_count
from .sync import (
    build_package,
    get_config,
    roundtrip_ok,
    set_cadence_days,
    sync_due,
    version_vector,
)

__all__ = [
    "SUBJECTS", "FRAMES", "KINDS", "base_dir",
    "intake", "ready_batches",
    "verify_batch",
    "refine_batch",
    "promote_batch", "revert_promotion", "store_count",
    "build_package", "get_config", "set_cadence_days", "sync_due",
    "version_vector", "roundtrip_ok",
]
