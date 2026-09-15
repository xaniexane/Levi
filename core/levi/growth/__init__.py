"""LEVI growth — raising baby Levi: a developmental learning loop.

Harvest experiences → reflect (rules offline, model when available) →
consolidate durable learnings into memory → journal every cycle.

Public API:
    run_cycle(use_model=True, dry_run=False, store=None) -> report dict
    status(store=None) -> dashboard dict
"""

from levi.growth.cycle import run_cycle, status
from levi.growth.experience import Experience, harvest_new
from levi.growth.journal import (
    developmental_stage,
    growth_dir,
    read_entries,
)
from levi.growth.reflect import Learning, reflect, reflect_rules

__all__ = [
    "run_cycle",
    "status",
    "Experience",
    "harvest_new",
    "Learning",
    "reflect",
    "reflect_rules",
    "developmental_stage",
    "growth_dir",
    "read_entries",
]
