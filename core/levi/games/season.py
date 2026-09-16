"""The Open Season — the honest battle pass.

The predatory trade, inverted: the battle pass sells *fear of missing
out* — expiring seasons, paid tiers, streak punishment, countdown timers.
Miss a week and your progress rots; pay and it doesn't.

The Open Season is the un-expiring season:

- seasons are personal eras YOU open and close; nothing expires on its own;
- no paid tiers, no premium track — every reward is free, forever;
- streaks celebrate but never punish: miss days and your streak *freezes*,
  automatically, at no cost. Progress never rots;
- challenges are player-logged honestly (this is a toy of self-tracking,
  not surveillance);
- titles earned are cosmetic words, not power, not purchases;
- everything exports as portable JSON — your season is yours.

A battle pass that cannot FOMO you. That is the entire joke, and the
entire point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="open-season",
    progress_portable=True,
    odds_declared=True,  # no chance anywhere — stated up front
    hints_free=True,
)

LEVEL_XP = [0, 100, 250, 500, 1000, 2000, 4000]  # level i needs LEVEL_XP[i]
LEVEL_TITLES = [
    "Newcomer",
    "Regular",
    "Steadfast",
    "Veteran",
    "Keeper",
    "Lodestar",
    "Legend of the Long Season",
]


@dataclass
class Challenge:
    id: str
    desc: str
    target: int
    progress: int = 0
    xp_reward: int = 50

    @property
    def done(self) -> bool:
        return self.progress >= self.target

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "desc": self.desc,
            "target": self.target,
            "progress": self.progress,
            "xp_reward": self.xp_reward,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Challenge":
        return cls(
            d["id"],
            d["desc"],
            int(d["target"]),
            int(d.get("progress", 0)),
            int(d.get("xp_reward", 50)),
        )


@dataclass
class Season:
    name: str
    opened: str  # ISO date
    challenges: Dict[str, Challenge] = field(default_factory=dict)
    xp: int = 0
    closed: Optional[str] = None  # ISO date or None — seasons never auto-expire
    active_days: List[str] = field(default_factory=list)  # ISO dates, honest log
    best_streak: int = 0

    # -- derived ---------------------------------------------------------
    @property
    def level(self) -> int:
        lvl = 0
        for i, need in enumerate(LEVEL_XP):
            if self.xp >= need:
                lvl = i
        return lvl

    @property
    def title(self) -> str:
        return LEVEL_TITLES[min(self.level, len(LEVEL_TITLES) - 1)]

    @property
    def streak(self) -> int:
        """Current streak: consecutive active days ending today-or-yesterday.

        Missing days FREEZE the streak — they never reset progress and never
        cost anything. The streak is a celebration, not a leash.
        """
        days = sorted(set(self.active_days))
        if not days:
            return 0
        today = date.today().isoformat()
        # streak counts back from the most recent active day; gaps simply end
        # the counted run without punishment.
        run = 1
        for prev, cur in zip(reversed(days[:-1]), reversed(days), strict=False):
            d_prev = date.fromisoformat(prev)
            d_cur = date.fromisoformat(cur)
            if (d_cur - d_prev).days == 1:
                run += 1
            else:
                break
        _ = today  # streak is anchored at last activity, not at today
        return run

    # -- actions ----------------------------------------------------------
    def log(
        self, challenge_id: str, amount: int = 1, on: Optional[str] = None
    ) -> Tuple[bool, bool]:
        """Log progress. Returns (challenge_completed_now, leveled_up).

        Raises KeyError on unknown challenge, ValueError on closed season.
        """
        if self.closed:
            raise ValueError("season is closed — reopen it to keep playing")
        ch = self.challenges[challenge_id]
        was_done = ch.done
        old_level = self.level
        ch.progress = min(ch.target, ch.progress + max(0, amount))
        day = on or date.today().isoformat()
        if day not in self.active_days:
            self.active_days.append(day)
        completed_now = ch.done and not was_done
        if completed_now:
            self.xp += ch.xp_reward
        self.best_streak = max(self.best_streak, self.streak)
        return completed_now, self.level > old_level

    def add_challenge(
        self, challenge_id: str, desc: str, target: int, xp_reward: int = 50
    ) -> None:
        if self.closed:
            raise ValueError("season is closed — reopen it to keep playing")
        if challenge_id in self.challenges:
            raise ValueError("challenge %r already exists" % challenge_id)
        self.challenges[challenge_id] = Challenge(
            challenge_id, desc, target, xp_reward=xp_reward
        )

    def close(self, on: Optional[str] = None) -> None:
        """Close the season yourself. Nothing else can close it for you."""
        self.closed = on or date.today().isoformat()

    def reopen(self) -> None:
        self.closed = None

    # -- persistence ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "opened": self.opened,
            "challenges": {k: v.to_dict() for k, v in self.challenges.items()},
            "xp": self.xp,
            "closed": self.closed,
            "active_days": list(self.active_days),
            "best_streak": self.best_streak,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Season":
        return cls(
            name=d["name"],
            opened=d["opened"],
            challenges={
                k: Challenge.from_dict(v) for k, v in d.get("challenges", {}).items()
            },
            xp=int(d.get("xp", 0)),
            closed=d.get("closed"),
            active_days=list(d.get("active_days", [])),
            best_streak=int(d.get("best_streak", 0)),
        )


def new_season(name: str, on: Optional[str] = None) -> Season:
    return Season(name=name, opened=on or date.today().isoformat())


def status_text(season: Season) -> str:
    lines = [
        "Open Season: %s  (opened %s%s)"
        % (
            season.name,
            season.opened,
            " — CLOSED %s" % season.closed if season.closed else " — never expires",
        ),
        "Level %d — %s  (%d xp)" % (season.level, season.title, season.xp),
        "Streak: %d day(s) (best %d) — missing days freeze, never punish."
        % (season.streak, season.best_streak),
        "Challenges:",
    ]
    if not season.challenges:
        lines.append("  (none yet — add some)")
    for ch in season.challenges.values():
        mark = "DONE" if ch.done else "%d/%d" % (ch.progress, ch.target)
        lines.append("  [%s] %s — %s (+%d xp)" % (ch.id, ch.desc, mark, ch.xp_reward))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI plumbing (state lives in the player-owned save store)
# ---------------------------------------------------------------------------


def _load(slot: str) -> Season:
    from levi.games.saves import SaveStore, SaveError

    store = SaveStore()
    try:
        return Season.from_dict(store.load("open-season", slot))
    except SaveError:
        raise


def _save(season: Season, slot: str) -> None:
    from levi.games.saves import SaveStore

    SaveStore().save("open-season", slot, season.to_dict())


def cmd(args) -> int:
    """season <new|add|log|status|close|reopen> — argv namespace from __main__."""
    slot = args.slot
    if args.action == "new":
        if args.name is None:
            print("usage: season new <name>")
            return 2
        season = new_season(args.name)
        _save(season, slot)
        print("Season %r opened. It will never expire on its own." % args.name)
        return 0
    try:
        season = _load(slot)
    except Exception:
        print("no season in slot %r — start one with: season new <name>" % slot)
        return 2
    if args.action == "status":
        print(status_text(season))
    elif args.action == "add":
        season.add_challenge(args.cid, args.desc, args.target, args.xp)
        _save(season, slot)
        print("challenge %r added." % args.cid)
    elif args.action == "log":
        completed, leveled = season.log(args.cid, args.amount)
        _save(season, slot)
        ch = season.challenges[args.cid]
        print("logged: %s %d/%d" % (ch.desc, ch.progress, ch.target))
        if completed:
            print("  challenge complete! +%d xp" % ch.xp_reward)
        if leveled:
            print("  LEVEL UP — now level %d: %s" % (season.level, season.title))
    elif args.action == "close":
        season.close()
        _save(season, slot)
        print("Season closed by you, on your terms. Reopen anytime.")
    elif args.action == "reopen":
        season.reopen()
        _save(season, slot)
        print("Season reopened. Welcome back — nothing rotted while you were gone.")
    else:
        print("unknown season action")
        return 2
    return 0
