"""LEVI doors — the door-plugin contract for LEVI games.

REMIX DELTA: BBS door games (LoRD 1989, TradeWars) ran as external
programs chained from the BBS via "drop files" (DOOR.SYS) carrying player
context — node, handle, time left, level — and daily-turn scarcity turned
play into appointment gaming: you came back tomorrow because your turns
were gone. The giants killed the pattern with infinite-scroll engagement
and pay-to-win. This module revives the door, not the bulletin board:

- :mod:`levi.doors.doors` — a clean-room JSON drop-file contract
  (node, handle, time-left, level — NOT DOOR.SYS-compatible, deliberately;
  DOS-era bytes stay in the museum), a daily-turn scarcity engine keyed on
  UTC days (UTC midnight resets, no timezone arguments), and a sample door
  (the number oracle) that demonstrates the contract end to end.
- Drop files are data, never code: a door reads the JSON and prints to
  stdout; nothing executes anything.
- State lives under ``~/.levi/doors/`` — owner-only (0700 dirs, 0600
  files), stdlib-only, no network, no sleeps.

What it ADDS that the giants refuse:
- Appointment gaming by design: a turn budget that resets once a day,
  not a stamina meter you can pay to refill.
- A stable interop surface: any LEVI-native door speaks the same
  drop-file contract and the same turn ledger.

Relationship to the rest of LEVI: doors are LEVI-native additions and
are deliberately separate from :mod:`levi.games` — doors are external
programs chained through the drop-file contract, not in-process games.

Run: ``python -m levi.doors --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
    "HOME_DIRNAME",
]

HOME_DIRNAME = "doors"

SHELF = {
    "name": "doors contract",
    "summary": (
        "BBS door games revived: a clean-room JSON drop-file contract "
        "(node/handle/time-left/level — not DOOR.SYS-compatible), a "
        "daily-turn scarcity engine keyed on UTC days, and a sample "
        "door (the number oracle). Owner-only state under ~/.levi/doors/; "
        "separate from levi.games."
    ),
    "items": [
        "doors: write_drop/read_drop JSON drop-file contract, 0600 perms",
        "doors: TurnLedger — per_day turns per player per door, UTC-day reset, atomic persist",
        "doors: play_oracle — sample door, deterministic daily target, higher/lower/correct",
        "CLI: python -m levi.doors drop|turn|play",
    ],
}
