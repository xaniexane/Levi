"""LEVI Games Warehouse — fair-play additions, never predatory rebuilds.

Honest local games with fair mechanics and player-owned progress, stocked
by the perpetual hunt's games theme (dead genres, forgotten mechanics,
killed platforms, predatory monetization trades — remixed as additions).

Contents:
- :mod:`levi.games.charter` — the Fair Play Charter: honest-design rules
  every LEVI game must pass (machine-checkable).
- :mod:`levi.games.saves` — portable, player-owned save files.
- :mod:`levi.games.deduction` — Codebreak: a Mastermind-style deduction game.
- :mod:`levi.games.daily_puzzle` — the Daily Cipher: a deterministic,
  FOMO-free daily substitution-cipher puzzle with free unlimited hints.
- :mod:`levi.games.hotseat` — pass-and-play local multiplayer (TicTacToe,
  Nim): the forgotten couch mechanic, revived without accounts or servers.

Play: ``python -m levi.games charter`` / ``play codebreak|tictactoe|nim`` /
``cipher [--date YYYY-MM-DD]`` / ``saves ...``
"""

from levi.games import charter, daily_puzzle, deduction, hotseat, saves

__all__ = ["charter", "deduction", "daily_puzzle", "hotseat", "saves"]
