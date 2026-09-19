"""LEVI engagement layer — fun surveys + campaigns, local-first.

The familiarization-phase instrument: standalone drops introduce
capabilities, users play through surveys and campaigns, and everything
circles back full circle into the hub — completed surveys/campaigns
report *aggregate learnings* (never individual answers) to DemandPulse's
store so the organism learns what users care about.

Doctrine, enforced in code:
- Opt-in always. Nothing engages the user until they opt in.
- Skippable always. Every question skippable; any survey abortable.
- User controls frequency: off / daily / weekly.
- Local-first. Answers live under ``~/.levi/engagement/`` (mode 600);
  nothing leaves the machine, ever.
- Analytics are metadata/counts only, composed with the inbox
  analytics module — no content, no arguments, no secrets.

Stdlib only.
"""

from .campaigns import CAMPAIGNS, get_campaign
from .prefs import Prefs, get_prefs
from .store import EngagementStore
from .surveys import SURVEYS, Question, Survey, get_survey, take_survey
from .voting import (
    BALLOTS,
    VERBS,
    Ballot,
    cast_favorite,
    cast_proposal,
    get_ballot,
    run_ballot_interactive,
)

__all__ = [
    "BALLOTS",
    "CAMPAIGNS",
    "SURVEYS",
    "VERBS",
    "Ballot",
    "EngagementStore",
    "Prefs",
    "Question",
    "Survey",
    "cast_favorite",
    "cast_proposal",
    "get_ballot",
    "get_campaign",
    "get_prefs",
    "get_survey",
    "run_ballot_interactive",
    "take_survey",
]
