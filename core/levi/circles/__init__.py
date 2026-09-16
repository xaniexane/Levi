"""Circles — Dunbar-bounded trust circles (Path's cap, done right).

Path (2010-2018) had exactly one load-bearing idea: a hard cap on how
many people you can have, enforced by the app, explicitly inspired by
Robin Dunbar's work on human social capacity. The cap was the product —
intimacy by architecture, not by policy. Path died because a
growth-driven giant can't copy a cap: it would shrink the addressable
audience by definition.

LEVI has no growth pressure, no advertisers, no board, so the cap can
stay sacred. Circles are the local-first revival:

- Four Dunbar layers with HARD caps enforced at add-time (deny-closed):
  inner (5), close (15), friends (50), tribe (150).
- Members are local ids — no accounts, no servers, no friend requests.
- Sharing is circle-scoped: a payload goes to exactly one circle and
  the receipt records the circle and a snapshot of who was in it. There
  is no public feed anywhere in the design.
- No public counts: the store never publishes network size. An
  owner-only ``audit`` shows cap headroom honestly (what the cap
  protects you from is growth theater, not the keeper's own numbers).
- Path's own warning is honored: they lifted the cap themselves
  (50 -> 150 -> 500) chasing growth. Here the caps are constants in
  code, and raising one is a deliberate, visible code change — never a
  silent policy drift.

Safety boundaries: owner-only storage (dir 0700, file 0600). Shares are
local receipts — this module has no network transport; handing a share
to someone uses the community export path or the telegraph office.
"""

from __future__ import annotations

__all__ = ["SHELF", "HOME_DIRNAME", "LAYERS", "CircleError"]

HOME_DIRNAME = "circles"

#: (layer_name, hard_cap) — the sacred constants. Changing these is a
#: product decision, never a silent drift.
LAYERS = (
    ("inner", 5),
    ("close", 15),
    ("friends", 50),
    ("tribe", 150),
)


class CircleError(Exception):
    """A circle operation was refused (cap hit, bad layer, duplicate)."""


SHELF = {
    "name": "circles",
    "summary": (
        "Dunbar-bounded trust circles: hard-capped layers (5/15/50/150) "
        "enforced at add-time, circle-scoped share receipts, owner-only "
        "local store. Path's cap revived without Path's growth pressure."
    ),
    "items": [
        "layers: add/remove/move members with hard caps, deny-closed",
        "share: circle-scoped share receipts with member snapshots",
        "audit: owner-only cap headroom, no public counts",
        "CLI: python -m levi.circles add|remove|move|list|audit|share",
    ],
}
