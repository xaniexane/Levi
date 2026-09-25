"""Engagement preferences — opt-in, skippable, user-controlled frequency.

Nothing engages the user until they explicitly opt in. Frequency is
theirs: off (never prompt), daily (new items surface once a day),
weekly (once a week). Stored locally as ``prefs.json``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional

_ENV_DIR = "LEVI_ENGAGEMENT_DIR"
FREQUENCIES = ("off", "daily", "weekly")


def default_engagement_dir() -> Path:
    override = os.environ.get(_ENV_DIR, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi" / "engagement"


@dataclass
class Prefs:
    opted_in: bool = False
    frequency: str = "weekly"
    last_prompt: str = ""  # ISO date of last proactive prompt

    def __post_init__(self) -> None:
        if self.frequency not in FREQUENCIES:
            self.frequency = "weekly"

    def can_prompt_today(self) -> bool:
        """True only when opted in, frequency on, and not already prompted."""
        if not self.opted_in or self.frequency == "off":
            return False
        today = date.today().isoformat()
        if self.frequency == "daily":
            return self.last_prompt != today
        # weekly: prompt at most once per 7-day window; empty counts as due
        if not self.last_prompt:
            return True
        try:
            delta = date.fromisoformat(today) - date.fromisoformat(self.last_prompt)
        except ValueError:
            return True
        return delta.days >= 7


def get_prefs(base_dir: Optional[Path] = None) -> Prefs:
    base = Path(base_dir) if base_dir else default_engagement_dir()
    path = base / "prefs.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return Prefs()
    if not isinstance(raw, dict):
        return Prefs()
    return Prefs(
        opted_in=bool(raw.get("opted_in", False)),
        frequency=str(raw.get("frequency", "weekly")),
        last_prompt=str(raw.get("last_prompt", "")),
    )


def save_prefs(prefs: Prefs, base_dir: Optional[Path] = None) -> bool:
    base = Path(base_dir) if base_dir else default_engagement_dir()
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(base, 0o700)
        tmp = base / "prefs.json.tmp"
        tmp.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")
        tmp.replace(base / "prefs.json")
        return True
    except OSError:
        return False
