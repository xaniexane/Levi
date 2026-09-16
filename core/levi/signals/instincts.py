"""Evidence-triggered instincts with cooldowns and grade caps.

An instinct is a tiny spec, not a vibe meter::

    id:        instinct.two_miss
    fires_on:  commitments.missed>=2
    cooldown:  86400          # seconds
    max_grade: ESCALATE
    does:      quote the original lock; ask for a new time or an explicit drop

``fires_on`` names an evidence key (``commitments.missed``,
``logs.error_spike``, ``focus.empty_block``) and may carry a comparison
(``>=2``, ``==true``). No evidence, no fire — never on vibes.

Cooldown state lives at ``<levi-home>/signals/cooldowns.json`` and is
resolved at call time from ``$LEVI_HOME`` (else ``~/.levi``); it is never
hardcoded and never read at import time. An instinct that fires records
its timestamp; a second evaluation inside the cooldown window produces
nothing.

Grade caps are enforced by clamping: an instinct's handler may build any
signal, but the plane downgrades anything above ``max_grade`` before it
is returned. An instinct NEVER emits above its max grade.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.signals.grades import Signal, SignalGrade

__all__ = [
    "Instinct",
    "InstinctRegistry",
    "levi_home",
    "matches_evidence",
]

_COOLDOWN_FILE = "cooldowns.json"
_SIGNALS_DIR = "signals"

_FIRES_ON_RE = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*(>=|<=|==|!=|>|<)?\s*(.*?)\s*$")


def levi_home() -> Path:
    """LEVI state home: ``$LEVI_HOME`` when set (hermetic tests), else ``~/.levi``.

    Resolved at call time — never at import — so tests can redirect it.
    """
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _coerce_number(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def matches_evidence(fires_on: str, evidence: Dict[str, Any]) -> bool:
    """Evaluate a ``fires_on`` spec against an evidence dict.

    Bare key (``focus.empty_block``) fires when the value is truthy.
    Suffixed comparisons (``commitments.missed>=2``) fire when the
    comparison holds. Missing keys never fire.
    """
    match = _FIRES_ON_RE.match(fires_on or "")
    if not match:
        return False
    key, op, raw_threshold = match.groups()
    if key not in evidence:
        return False
    value = evidence[key]
    if not op:
        return bool(value)
    threshold = _coerce_number(raw_threshold)
    try:
        if op == ">=":
            return value >= threshold  # type: ignore[operator]
        if op == "<=":
            return value <= threshold  # type: ignore[operator]
        if op == ">":
            return value > threshold  # type: ignore[operator]
        if op == "<":
            return value < threshold  # type: ignore[operator]
        if op == "==":
            return value == threshold
        if op == "!=":
            return value != threshold
    except TypeError:
        return False
    return False  # pragma: no cover - unreachable


@dataclass
class Instinct:
    """One evidence-triggered instinct."""

    id: str
    fires_on: str
    cooldown: int  # seconds
    max_grade: SignalGrade
    does: str
    handler: Optional[Callable[[Dict[str, Any]], Optional[Signal]]] = None
    tag: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("instinct id must be non-empty")
        if not isinstance(self.cooldown, int) or self.cooldown < 0:
            raise ValueError("cooldown must be a non-negative int (seconds)")
        if not isinstance(self.max_grade, SignalGrade):
            raise TypeError("max_grade must be a SignalGrade")
        if not self.fires_on or not _FIRES_ON_RE.match(self.fires_on):
            raise ValueError("bad fires_on spec %r" % (self.fires_on,))
        if not self.tag:
            short = self.id.split(".")[-1]
            self.tag = "[%s]" % short


class InstinctRegistry:
    """Holds instincts; evaluates evidence into grade-capped signals.

    ``home`` is the LEVI state home (cooldown state lives under
    ``<home>/signals/``). Pass ``home=`` for hermetic tests; otherwise it
    is resolved at call time via :func:`levi_home`.
    """

    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self._home_override = Path(home).expanduser() if home is not None else None
        self._instincts: Dict[str, Instinct] = {}

    # -- home / state --------------------------------------------------------

    def _home(self) -> Path:
        return self._home_override if self._home_override is not None else levi_home()

    def _state_path(self) -> Path:
        return self._home() / _SIGNALS_DIR / _COOLDOWN_FILE

    def _load_state(self) -> Dict[str, str]:
        try:
            raw = json.loads(self._state_path().read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_state(self, state: Dict[str, str]) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(path)

    # -- registry ------------------------------------------------------------

    def register(self, instinct: Instinct) -> Instinct:
        """Register an instinct; duplicate ids are rejected."""
        if instinct.id in self._instincts:
            raise ValueError("instinct %r already registered" % instinct.id)
        self._instincts[instinct.id] = instinct
        return instinct

    def list(self) -> List[Instinct]:
        return list(self._instincts.values())

    def get(self, instinct_id: str) -> Optional[Instinct]:
        return self._instincts.get(instinct_id)

    def reset_cooldown(self, instinct_id: str) -> None:
        """Clear one instinct's cooldown (diagnostics / tests)."""
        state = self._load_state()
        state.pop(instinct_id, None)
        self._save_state(state)

    # -- evaluation ----------------------------------------------------------

    @staticmethod
    def _now_utc(now: Optional[datetime]) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if now.tzinfo is None:
            # Naive datetimes are local time, not UTC.
            return now.astimezone()
        return now.astimezone(timezone.utc)

    def _on_cooldown(
        self, instinct: Instinct, state: Dict[str, str], now: datetime
    ) -> bool:
        raw = state.get(instinct.id)
        if not raw:
            return False
        try:
            last = datetime.fromisoformat(raw)
        except ValueError:
            return False
        if last.tzinfo is None:
            # Naive stored timestamps are local time, not UTC.
            last = last.astimezone()
        return (now - last).total_seconds() < instinct.cooldown

    def _clamp_grade(self, signal: Signal, instinct: Instinct) -> Signal:
        """Enforce the grade cap: never emit above ``max_grade``."""
        if signal.grade.value <= instinct.max_grade.value:
            return signal
        clamped = Signal(
            grade=instinct.max_grade,
            tag=signal.tag,
            title=signal.title,
            body=signal.body
            + (
                "\n[grade clamped to %s by instinct %s]"
                % (instinct.max_grade.name, instinct.id)
            ),
            actions=signal.actions,
            requires_ack=signal.requires_ack
            and instinct.max_grade is SignalGrade.ESCALATE,
            due_now=signal.due_now,
            source=signal.source or instinct.id,
        )
        return clamped

    def evaluate(
        self, evidence: Dict[str, Any], now: Optional[datetime] = None
    ) -> List[Signal]:
        """Evaluate every instinct against evidence → capped signals.

        Instincts with no matching evidence stay silent; instincts inside
        their cooldown window produce nothing and do not refresh the
        cooldown. ``now`` is injectable for tests.
        """
        moment = self._now_utc(now)
        state = self._load_state()
        fired: List[Signal] = []
        dirty = False
        for instinct in self._instincts.values():
            if not matches_evidence(instinct.fires_on, evidence):
                continue
            if self._on_cooldown(instinct, state, moment):
                continue
            signal = (
                instinct.handler(evidence) if instinct.handler is not None else None
            )
            if signal is None:
                signal = Signal(
                    grade=instinct.max_grade,
                    tag=instinct.tag,
                    title=instinct.does,
                    source=instinct.id,
                )
            signal = self._clamp_grade(signal, instinct)
            if not signal.source:
                signal.source = instinct.id
            fired.append(signal)
            state[instinct.id] = moment.isoformat()
            dirty = True
        if dirty:
            self._save_state(state)
        return fired
