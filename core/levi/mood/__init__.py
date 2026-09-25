"""MOOD — honeypot decoy for abusive/snooping sessions.

Provenance (Chauncey, 2026-09-22):
    doom.py (struck play-to-lose engine; stored/2026-09-22-doom-engine/)
      -> mood (this module; the decoy reframing)

The old play-to-lose framing stays STRUCK. This is a honeypot: an open,
readable frame full of defensive booby traps for sessions Chauncey has
decided are abusive. Defensive blue-team only — observation and
containment, never counter-attack.

Modules:
  laws      — the declared invariants L1..L9 (law-guard-prove)
  tripwires — canary tokens, tripwire paths, snoop patterns (the traps)
  decoy     — the fake admin surface (canned, deterministic, never real)
  receipts  — hash-chained evidence receipts, append-only, 0600
  alert     — alert queue for Chauncey (the module writes; the host delivers)
  rate_limit — reversible escalation ladder (slow, contain, decay)
  routing   — the routing contract: explicit decision or no route (L1)

Routing policy is Chauncey's call. This module enforces the gate; it does
not make the decision.

Local-first, stdlib-only, no network, no subprocess. Records live under
a caller-supplied home (``~/.levi/mood/``).
"""

from __future__ import annotations

from levi.mood import alert, decoy, laws, rate_limit, receipts, routing, tripwires
from levi.mood.alert import AlertQueue
from levi.mood.decoy import MOOD_TAG, CANNED_COMMANDS, DecoyResponse, DecoySession
from levi.mood.laws import LAWS, LAW_NAMES, ZONE
from levi.mood.rate_limit import MAX_LEVEL, STEP_SECONDS, Escalation
from levi.mood.receipts import GENESIS_HEAD, Receipt, ReceiptWriter, mood_dir
from levi.mood.routing import (
    PolicyEntry,
    PolicyError,
    PolicyRequiredError,
    Router,
)
from levi.mood.tripwires import (
    CANARY_TOKENS,
    SNOOP_PATTERNS,
    TRIPWIRE_PATHS,
    TripEvent,
    TripwireKind,
    TripwireRegistry,
)

__all__ = [
    "LAW_NAMES",
    "LAWS",
    "ZONE",
    "MOOD_TAG",
    "CANNED_COMMANDS",
    "CANARY_TOKENS",
    "GENESIS_HEAD",
    "MAX_LEVEL",
    "SNOOP_PATTERNS",
    "STEP_SECONDS",
    "TRIPWIRE_PATHS",
    "AlertQueue",
    "DecoyResponse",
    "DecoySession",
    "Escalation",
    "PolicyEntry",
    "PolicyError",
    "PolicyRequiredError",
    "Receipt",
    "ReceiptWriter",
    "Router",
    "TripEvent",
    "TripwireKind",
    "TripwireRegistry",
    "alert",
    "decoy",
    "laws",
    "mood_dir",
    "rate_limit",
    "receipts",
    "routing",
    "tripwires",
]
