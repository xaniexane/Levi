"""Focus-mute contract — modes and what may speak in each.

Modes: ``focus`` | ``plan`` | ``review`` | ``play``.

The contract: in **focus** mode only due-now signals and ESCALATE
signals pass. Everything else is held — not downgraded, not queued
loudly, just not delivered. Quiet mode is equivalent to focus filtering.

The current mode persists at ``<levi-home>/signals/mode.json`` so a
foreground session and the daemon plane agree on it.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Union

from levi.signals.grades import Signal, SignalGrade
from levi.signals.instincts import levi_home

__all__ = ["Mode", "get_mode", "set_mode", "should_deliver", "quiet_delivers"]

_MODE_FILE = "mode.json"


class Mode(Enum):
    FOCUS = "focus"
    PLAN = "plan"
    REVIEW = "review"
    PLAY = "play"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


def _mode_path(home: "str | os.PathLike[str] | None") -> Path:
    base = Path(home).expanduser() if home is not None else levi_home()
    return base / "signals" / _MODE_FILE


def get_mode(home: "str | os.PathLike[str] | None" = None) -> Mode:
    """Current mode; defaults to PLAN when never set."""
    try:
        raw = json.loads(_mode_path(home).read_text(encoding="utf-8"))
        return Mode(str(raw.get("mode", "plan")))
    except (OSError, json.JSONDecodeError, ValueError):
        return Mode.PLAN


def set_mode(
    mode: Union[Mode, str], home: "str | os.PathLike[str] | None" = None
) -> Mode:
    """Persist the current mode."""
    mode = Mode(mode)
    path = _mode_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"mode": mode.value}, indent=2), encoding="utf-8")
    tmp.replace(path)
    return mode


def should_deliver(signal: Signal, mode: Union[Mode, str]) -> bool:
    """Focus-mute predicate.

    FOCUS: only ``due_now`` signals and ESCALATE pass. Every other grade
    is held silently. PLAN / REVIEW / PLAY: everything passes — muting is
    the active-hours gate's job there.
    """
    mode = Mode(mode)
    if mode is Mode.FOCUS:
        return signal.due_now or signal.grade is SignalGrade.ESCALATE
    return True


def quiet_delivers(signal: Signal) -> bool:
    """Quiet mode is equivalent to focus filtering."""
    return should_deliver(signal, Mode.FOCUS)
