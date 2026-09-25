"""DemandPulse — the $6/month standalone customer product.

Standalone product layer built ON TOP of the ``levi.demand`` sensing engine.
NEW FILES ONLY: nothing here edits the engine; the product wraps it with the
customer-facing shape Chauncey ordered for KFX2 production:

  product.py   — product definition, price anchor, 12% cut, honest limits
  payments.py  — payment/entitlement layer, STUBBED behind an explicit owner
                 gate. Charge path stays dark until Chauncey approves.
  ternary.py   — ternary signal states (dormant / gathering / breakout):
                 the skipped third state competitor binaries miss
  twins.py     — paired mind: Scout proposes, Verifier publishes/quarantines
  themes.py    — Myspace-style structured theme packs (safe, validated)
  quickstart.py — zero-config quickstart: keywords in, watches installed,
                  first digest path out
  briefing.py  — themed briefing renderer, file outbox only
  bundle.py    — release-bundle assembler (P4.1 shape); never installs or
                 delivers in this build — that stops at the owner gate
"""

from __future__ import annotations

from levi.demandpulse import (
    briefing as briefing,
    bundle as bundle,
    cli as cli,
    entitlements as entitlements,
    payments as payments,
    product as product,
    quickstart as quickstart,
    ternary as ternary,
    themes as themes,
    threat_signals as threat_signals,
    twins as twins,
    watch as watch,
)

__all__ = [
    "briefing",
    "bundle",
    "cli",
    "entitlements",
    "payments",
    "product",
    "quickstart",
    "ternary",
    "themes",
    "threat_signals",
    "twins",
    "watch",
]
