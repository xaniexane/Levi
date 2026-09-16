"""Door-plugin contract: JSON drop files, daily-turn scarcity, sample doors.

Revived from the BBS door era (LoRD/TradeWars) as a clean-room
LEVI-native remix — perpetual-hunt wave-008, research slug
``dead-networks-20260916``. Drop files carry player context the way
DOOR.SYS did, but as JSON with a ``levi-door-drop/1`` format marker
(NOT DOOR.SYS-compatible); the turn ledger gives every player a per-day
budget that resets at UTC midnight, creating appointment gaming.

stdlib only. No network, no sleeps, no subprocess.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import HOME_DIRNAME

DROP_FORMAT = "levi-door-drop/1"

REQUIRED_DROP_KEYS = ("node", "handle", "time_left_s", "level", "door")

ORACLE_DOOR = "oracle"


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _doors_dir() -> Path:
    p = _home() / HOME_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    return p


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


# ---------------------------------------------------------------- drop files


def write_drop(
    path: str | Path,
    *,
    node: str,
    handle: str,
    time_left_s: int,
    level: int,
    door: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write a JSON drop file carrying player context. Returns the path.

    The drop file is the contract between the launcher and the door:
    who the player is (handle), which node they came from, how much
    time they have left (time_left_s), their level, and which door they
    are entering. ``extra`` carries door-specific extras.
    """
    doc: Dict[str, Any] = {
        "format": DROP_FORMAT,
        "node": node,
        "handle": handle,
        "time_left_s": time_left_s,
        "level": level,
        "door": door,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "extra": dict(extra) if extra else {},
    }
    p = Path(path)
    if p.parent != Path("."):
        p.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(p, doc)
    return p


def read_drop(path: str | Path) -> Dict[str, Any]:
    """Read and validate a drop file. Raises ValueError on bad format."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("format") != DROP_FORMAT:
        raise ValueError("not a %r drop file" % DROP_FORMAT)
    missing = [k for k in REQUIRED_DROP_KEYS if k not in doc]
    if missing:
        raise ValueError("drop file missing keys: %s" % ", ".join(missing))
    return doc


# ------------------------------------------------- daily-turn scarcity


class TurnLedger:
    """Per-player, per-door daily turn budgets keyed on UTC days.

    Backed by ``~/.levi/doors/turns.json`` (or an explicit path), persisted
    atomically (temp file + os.replace). Days are UTC calendar days; a new
    UTC day means a fresh budget.
    """

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path is not None else _doors_dir() / "turns.json"

    @staticmethod
    def _check_per_day(per_day: int) -> None:
        if per_day < 1:
            raise ValueError("per_day must be >= 1, got %r" % (per_day,))

    @staticmethod
    def _key(player: str, door: str, day: date) -> str:
        return "%s\x00%s\x00%s" % (player, door, day.isoformat())

    @staticmethod
    def _day(today: Optional[date]) -> date:
        return today if today is not None else datetime.now(timezone.utc).date()

    def _load(self) -> Dict[str, int]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else {}

    def _save(self, data: Dict[str, int]) -> None:
        _write_json_atomic(self.path, data)

    def turns_left(
        self, player: str, door: str, per_day: int, today: Optional[date] = None
    ) -> int:
        """How many of today's turns remain for (player, door)."""
        self._check_per_day(per_day)
        used = self._load().get(self._key(player, door, self._day(today)), 0)
        return max(0, per_day - used)

    def spend_turn(
        self, player: str, door: str, per_day: int, today: Optional[date] = None
    ) -> bool:
        """Consume one turn; True if a turn was available, else False."""
        self._check_per_day(per_day)
        day = self._day(today)
        key = self._key(player, door, day)
        data = self._load()
        if data.get(key, 0) >= per_day:
            return False
        data[key] = data.get(key, 0) + 1
        self._save(data)
        return True


# ------------------------------------------------------- sample door


def oracle_target(handle: str, day: date, rng_seed_extra: str = "") -> int:
    """The oracle's target number (1..100), deterministic per day+handle.

    Derived from sha256 — stable within a UTC day, hermetic (no RNG
    state), so tests and replays agree.
    """
    seed = "%s:%s:%s:%s" % (handle, ORACLE_DOOR, day.isoformat(), rng_seed_extra)
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") % 100) + 1


def play_oracle(
    handle: str,
    guess: Optional[int] = None,
    *,
    per_day: int = 3,
    today: Optional[date] = None,
    rng_seed_extra: str = "",
) -> Dict[str, Any]:
    """Play one round of the number oracle.

    ``guess=None`` peeks at the game without spending a turn. A real
    guess spends one turn via the TurnLedger; out-of-range guesses raise
    ValueError without spending. Outcomes: prompt / higher / lower /
    correct / no-turns.
    """
    day = today if today is not None else datetime.now(timezone.utc).date()
    ledger = TurnLedger()
    if ledger.turns_left(handle, ORACLE_DOOR, per_day, today=day) <= 0:
        return {"outcome": "no-turns", "turns_left": 0}
    if guess is None:
        return {
            "outcome": "prompt",
            "range": [1, 100],
            "turns_left": ledger.turns_left(handle, ORACLE_DOOR, per_day, today=day),
        }
    if isinstance(guess, bool) or not isinstance(guess, int) or not 1 <= guess <= 100:
        raise ValueError("guess must be an int in 1..100, got %r" % (guess,))
    if not ledger.spend_turn(handle, ORACLE_DOOR, per_day, today=day):
        return {"outcome": "no-turns", "turns_left": 0}
    target = oracle_target(handle, day, rng_seed_extra)
    left = ledger.turns_left(handle, ORACLE_DOOR, per_day, today=day)
    if guess == target:
        return {"outcome": "correct", "turns_left": left}
    return {"outcome": "higher" if guess < target else "lower", "turns_left": left}
