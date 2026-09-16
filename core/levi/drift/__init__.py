"""Goal-drift instrument — notices when stated goals and actual behavior diverge.

Honest instrument, not a judge: it compares the trailing-14-day
activity tag distribution against stated goals and only raises a CARD
when the evidence (counts and concrete examples) supports it.
Below threshold it stays SILENT — no vague claims, ever.

All state in ``<LEVI_HOME>/drift/`` as local JSON.
"""

from .tracker import (
    DRIFT_THRESHOLD,
    WINDOW_DAYS,
    DriftTracker,
    set_goal,
    log_activity,
    weekly_card,
)

__all__ = [
    "DRIFT_THRESHOLD",
    "WINDOW_DAYS",
    "DriftTracker",
    "set_goal",
    "log_activity",
    "weekly_card",
]
