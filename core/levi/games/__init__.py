"""LEVI Games Warehouse — fair-play additions, never predatory rebuilds.

Honest local games with fair mechanics and player-owned progress, stocked
by the perpetual hunt's games theme (dead genres, forgotten mechanics,
killed platforms, predatory monetization trades — remixed as additions).

Contents:
- :mod:`levi.games.charter` — the Fair Play Charter: honest-design rules
  every LEVI game must pass (machine-checkable).
- :mod:`levi.games.saves` — portable, player-owned save files.
- :mod:`levi.games.sunset` — sunset escrow: the funeral planned at birth.
- :mod:`levi.games.deduction` — Codebreak: a Mastermind-style deduction game.
- :mod:`levi.games.daily_puzzle` — the Daily Cipher: a deterministic,
  FOMO-free daily substitution-cipher puzzle with free unlimited hints.
- :mod:`levi.games.hotseat` — pass-and-play local multiplayer (TicTacToe,
  Nim): the forgotten couch mechanic, revived without accounts or servers.
- :mod:`levi.games.bagatelle` — Bagatelle: mechanical-pinball remix with
  shareable board layouts and a prove-the-odds audit mode.
- :mod:`levi.games.mancala` — Mancala: the parametric game grammar; rules
  are data, variants are generated and self-play-validated.
- :mod:`levi.games.parlor` — the Parlor: the third place that cannot be
  starved — handles, a feed-free bulletin board, and game nights, all in
  one portable file (the PlayStation Home / Miiverse / Club Penguin /
  AltspaceVR inversion).
- :mod:`levi.games.guestplay` — guest kits: the DS Download Play
  revival. The host exports a signed kit (rules, data, session token);
  guests play with nothing installed and keep nothing afterward.
  Possession is the license, expiry is the clock.
- :mod:`levi.games.proxypass` — encounter envelopes: the 3DS StreetPass
  revival. Signed, minimal, anonymous hello packets over a local drop
  directory — rate limits and blocklists from day one, no cloud.

Play: ``python -m levi.games charter`` / ``play codebreak|tictactoe|nim`` /
``cipher [--date YYYY-MM-DD]`` / ``bagatelle`` / ``mancala`` / ``saves ...``
/ ``parlor covenant``
"""

from levi.games import (
    bagatelle,
    charter,
    daily_puzzle,
    deduction,
    hotseat,
    mancala,
    parlor,
    saves,
    sunset,
)

__all__ = [
    "bagatelle",
    "charter",
    "deduction",
    "daily_puzzle",
    "hotseat",
    "mancala",
    "parlor",
    "saves",
    "sunset",
]
