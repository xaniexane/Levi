"""Arcade League — the local high-score cabinet, revived.

Two dead arcade mechanics, native LEVI form:

1. Score attack + initials leaderboard. The top-10 table lives in an
   owner-only JSON file under ``~/.levi/games/league/<game_id>.json`` —
   carved on the cabinet, owned by the room. No account, no server, no
   ladder to monetize, no revocation path (cf. arch-games-stadia-vanishing-
   library and arch-games-predatory-monetization-trades).

2. Attract mode. The game plays itself — seeded AI-vs-AI demo matches
   (PIX vs BIT) over the real HotseatGame surface, printed to the
   terminal. The advertisement cannot lie: it IS the gameplay. Doubles
   as a smoke test for any game plugged into the hotseat surface
   (cf. arch-games-attract-mode).

Honesty rules, enforced by the Fair Play Charter:
- Scores are honestly labeled ``played`` (came through a game session),
  ``submitted`` (a claim, e.g. typed at the CLI), or ``attract``
  (demo matches never touch player tables).
- Deterministic games may carry a ``seed``/``replay`` so a claimed
  score can be re-verified; verified entries are marked as such.
- Initials are 3 sanitized characters (uppercase alnum), the arcade
  constraint, and deny-closed: bad entries are refused, never mangled.

Usage: ``python -m levi.games.league <table|submit|attract> ...``
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="league",
    progress_portable=True,
    odds_declared=True,
    has_randomness=False,  # attract AI uses seeded RNG; scores are not chance-based
    requires_network=False,
)

LEAGUE_FORMAT = 1
TABLE_LIMIT = 10
INITIALS_LEN = 3


class LeagueError(Exception):
    """Deny-closed league failures."""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _default_root() -> Path:
    home = os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi")
    return Path(home) / "games" / "league"


def _safe_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "-_").strip("-_")
    if not safe:
        raise LeagueError("bad game id %r" % name)
    return safe


def sanitize_initials(initials: str) -> str:
    """The arcade constraint: 3 uppercase alnum characters, or refuse."""
    if not isinstance(initials, str):
        raise LeagueError("initials must be a string")
    clean = "".join(c for c in initials.upper() if c.isalnum())
    if len(clean) != INITIALS_LEN:
        raise LeagueError(
            "initials must be exactly %d letters/digits (got %r)"
            % (INITIALS_LEN, initials)
        )
    return clean


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


@dataclass
class ScoreEntry:
    initials: str
    score: int
    date: str  # ISO date
    provenance: str = "submitted"  # played | submitted | attract
    verified: bool = False
    seed: Optional[int] = None
    replay: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ScoreEntry":
        return cls(
            initials=data["initials"],
            score=int(data["score"]),
            date=data["date"],
            provenance=data.get("provenance", "submitted"),
            verified=bool(data.get("verified", False)),
            seed=data.get("seed"),
            replay=data.get("replay"),
        )


class ScoreTable:
    """One game's top-10 cabinet table. Deny-closed on bad input."""

    def __init__(
        self,
        game_id: str,
        higher_is_better: bool = True,
        limit: int = TABLE_LIMIT,
        root: "str | os.PathLike[str] | None" = None,
    ):
        self.game_id = _safe_name(game_id)
        self.higher_is_better = higher_is_better
        self.limit = max(1, int(limit))
        self.root = Path(root) if root else _default_root()
        self._entries: List[ScoreEntry] = []
        self._load()

    # -- persistence ------------------------------------------------------
    def _path(self) -> Path:
        return self.root / (self.game_id + ".json")

    def _load(self) -> None:
        p = self._path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LeagueError(
                "corrupt league table %s: %s" % (self.game_id, exc)
            ) from exc
        if not isinstance(data, dict) or data.get("format") != LEAGUE_FORMAT:
            raise LeagueError("unsupported league format for %s" % self.game_id)
        self._entries = [ScoreEntry.from_dict(e) for e in data.get("entries", [])]
        self._sort()

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        p = self._path()
        tmp = p.with_suffix(".tmp")
        payload = {
            "format": LEAGUE_FORMAT,
            "game_id": self.game_id,
            "higher_is_better": self.higher_is_better,
            "entries": [e.to_dict() for e in self._entries],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    # -- ranking ----------------------------------------------------------
    def _sort(self) -> None:
        self._entries.sort(key=lambda e: e.score, reverse=self.higher_is_better)

    def table(self) -> List[ScoreEntry]:
        return list(self._entries)

    def submit(
        self,
        initials: str,
        score: int,
        *,
        provenance: str = "submitted",
        seed: Optional[int] = None,
        replay: Optional[str] = None,
        verified: bool = False,
    ) -> int:
        """Submit a score. Returns rank (0-based) or -1 if it didn't make the table."""
        tag = sanitize_initials(initials)
        if not isinstance(score, int):
            raise LeagueError("score must be an integer")
        if provenance not in ("played", "submitted", "attract"):
            raise LeagueError("bad provenance %r" % provenance)
        entry = ScoreEntry(
            initials=tag,
            score=score,
            date=datetime.now(timezone.utc).date().isoformat(),
            provenance=provenance,
            verified=verified,
            seed=seed,
            replay=replay,
        )
        self._entries.append(entry)
        self._sort()
        self._entries = self._entries[: self.limit]
        self._save()
        try:
            return self._entries.index(entry)
        except ValueError:
            return -1

    def rank_of(self, initials: str, score: int) -> int:
        """Where WOULD this score land, without submitting? -1 = off the table."""
        tag = sanitize_initials(initials)
        probe = ScoreEntry(tag, score, "1970-01-01", provenance="submitted")
        trial = sorted(
            self._entries + [probe],
            key=lambda e: e.score,
            reverse=self.higher_is_better,
        )[: self.limit]
        try:
            return trial.index(probe)
        except ValueError:
            return -1

    def clear(self) -> None:
        """Empty the table (the cabinet gets unplugged)."""
        self._entries = []
        self._save()


# ---------------------------------------------------------------------------
# Attract mode — the game plays itself
# ---------------------------------------------------------------------------


def _load_tables() -> Dict[str, type]:
    from levi.games import hotseat

    return dict(hotseat.TABLES)


def attract(
    game: str = "tictactoe",
    rounds: int = 3,
    seed: int = 0,
    out=None,
) -> List[Optional[int]]:
    """Run seeded AI-vs-AI demo matches over the real HotseatGame surface.

    Returns the winner index of each round (0 = PIX, 1 = BIT, -1 = draw,
    None = game never finished). Attract games never touch player tables.
    """
    out = out if out is not None else sys.stdout
    tables = _load_tables()
    if game not in tables:
        raise LeagueError(
            "attract knows %s (try: %s)" % (game, ", ".join(sorted(tables)))
        )
    names = ("PIX", "BIT")
    winners: List[Optional[int]] = []
    rng = random.Random(seed)
    for rnd in range(max(0, rounds)):
        g = tables[game]()
        moves: List[str] = []
        guard = 0
        while g.winner() is None and guard < 1000:
            move = rng.choice(g.legal_moves())
            g.apply_move(move)
            moves.append(move)
            guard += 1
        w = g.winner()
        winners.append(w)
        tag = names[w] if w in (0, 1) else ("DRAW" if w == -1 else "UNFINISHED")
        out.write(
            "attract %s round %d (seed %d, %d moves): %s wins\n%s\n\n"
            % (game, rnd + 1, seed, len(moves), tag, g.describe())
        )
    return winners


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def render_table(table: ScoreTable) -> str:
    rows = ["%-4s %-4s %8s  %s" % ("RANK", "TAG", "SCORE", "DATE/PROV")]
    rows.append("-" * 44)
    for i, e in enumerate(table.table(), start=1):
        flag = "✓" if e.verified else " "
        rows.append(
            "%-4d %-4s %8d  %s %s%s"
            % (i, e.initials, e.score, e.date, e.provenance, flag)
        )
    if not table.table():
        rows.append("(empty — be the first to carve your initials)")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_table(args) -> int:
    t = ScoreTable(args.game, higher_is_better=not args.lower_wins)
    print(render_table(t))
    return 0


def _cmd_submit(args) -> int:
    t = ScoreTable(args.game, higher_is_better=not args.lower_wins)
    rank = t.submit(
        args.initials,
        args.score,
        seed=args.seed,
        replay=args.replay,
        verified=args.verified,
    )
    if rank >= 0:
        print("carved: %s #%d on the %s cabinet" % (args.game, rank + 1, args.game))
    else:
        print(
            "didn't make the top %d — the cabinet remembers, but not publicly" % t.limit
        )
    return 0


def _cmd_attract(args) -> int:
    attract(args.game, rounds=args.rounds, seed=args.seed)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.games.league",
        description="Arcade League: local high-score cabinets + attract mode.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("table", help="show a game's cabinet table")
    p.add_argument("game")
    p.add_argument("--lower-wins", action="store_true", help="lower score ranks first")
    p.set_defaults(func=_cmd_table)

    p = sub.add_parser("submit", help="submit a score to the cabinet")
    p.add_argument("game")
    p.add_argument("initials", help="exactly 3 letters/digits, arcade style")
    p.add_argument("score", type=int)
    p.add_argument("--lower-wins", action="store_true")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--replay", default=None)
    p.add_argument("--verified", action="store_true")
    p.set_defaults(func=_cmd_submit)

    p = sub.add_parser("attract", help="watch the game play itself (honest demo)")
    p.add_argument("game", nargs="?", default="tictactoe")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=_cmd_attract)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
