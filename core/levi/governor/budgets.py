"""Per-session and per-day token budgets, enforced deny-closed.

Defaults are sane starting points, not science: a runaway agent loop
should hit the session budget long before it hurts, and the day budget
catches slow-burn abuse. Everything is configurable in
``~/.levi/governor/config.json``.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time

from levi.governor.meter import Meter, governor_home

DEFAULT_BUDGETS = {
    "session_tokens": 200_000,
    "day_tokens": 2_000_000,
}


class BudgetEnforcer:
    """Deny-closed budget checks against the meter ledger."""

    def __init__(
        self,
        meter: Meter | None = None,
        home: "str | os.PathLike[str] | None" = None,
        config: dict | None = None,
        clock=time.time,
    ) -> None:
        self._dir = governor_home(home)
        self._config_file = self._dir / "config.json"
        self._meter = meter if meter is not None else Meter(home=home, clock=clock)
        self._clock = clock
        self._session_used = 0
        self._budgets = dict(DEFAULT_BUDGETS)
        self._budgets.update(self._load_config())
        if config:
            for k, v in config.items():
                if k in self._budgets:
                    self._budgets[k] = int(v)

    # -- config ---------------------------------------------------------
    def _load_config(self) -> dict:
        if not self._config_file.exists():
            return {}
        try:
            raw = json.loads(self._config_file.read_text(encoding="utf-8"))
            return {k: int(v) for k, v in raw.items() if k in DEFAULT_BUDGETS}
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return {}  # corrupt config: fall back to defaults, never crash

    def set_budget(self, name: str, tokens: int) -> None:
        """Persist a budget change (operator action)."""
        if name not in DEFAULT_BUDGETS:
            raise ValueError(f"unknown budget {name!r}")
        if tokens <= 0:
            raise ValueError("budget must be positive")
        self._budgets[name] = int(tokens)
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._config_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._budgets, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._config_file)

    # -- accounting -----------------------------------------------------
    def note_spend(self, tokens: int) -> None:
        """Count tokens toward the session budget (called after each call)."""
        if tokens < 0:
            raise ValueError("token counts must be non-negative")
        self._session_used += int(tokens)

    def session_used(self) -> int:
        return self._session_used

    def day_used(self) -> int:
        """Tokens metered since local midnight (reads the ledger)."""
        midnight = (
            _dt.datetime.now()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        return self._meter.totals(since=midnight)["total_tokens"]

    def remaining(self) -> dict:
        return {
            "session_tokens": {
                "budget": self._budgets["session_tokens"],
                "used": self.session_used(),
                "remaining": max(
                    0, self._budgets["session_tokens"] - self.session_used()
                ),
            },
            "day_tokens": {
                "budget": self._budgets["day_tokens"],
                "used": self.day_used(),
                "remaining": max(0, self._budgets["day_tokens"] - self.day_used()),
            },
        }

    def authorize(self, extra_tokens: int = 0) -> tuple[bool, str]:
        """Deny-closed: is there budget for ``extra_tokens`` more?"""
        if extra_tokens < 0:
            return False, "negative token estimate refused"
        sess = self.session_used() + extra_tokens
        if sess > self._budgets["session_tokens"]:
            return (
                False,
                f"session budget exhausted: {self.session_used():,} used of "
                f"{self._budgets['session_tokens']:,} tokens",
            )
        day = self.day_used() + extra_tokens
        if day > self._budgets["day_tokens"]:
            return (
                False,
                f"daily budget exhausted: {self.day_used():,} used of "
                f"{self._budgets['day_tokens']:,} tokens",
            )
        return True, "within budget"
