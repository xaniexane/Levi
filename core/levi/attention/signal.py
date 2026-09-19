"""The AttentionBus: SELCAL for the machine.

A wake code is a two-part tuple, e.g. ("growth", "tick") — SELCAL's two
tone pairs, as strings. Services subscribe with their code. The bus is
silent by default: ``signal()`` returns only the subscribers whose code
matches. Unmatched signals are not dropped silently; they are counted in
the wake ledger, so attention spending is auditable.

Honest limits, carried over from SELCAL itself:
- a wake code is a summons, never an identity (SELCAL's duplicate codes
  prove addressing is not authentication);
- the bus delivers to local subscribers only; it is not a message queue,
  not a credential, not a lock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

WakeCode = Tuple[str, str]

_CODE_PART = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

__all__ = ["AttentionBus", "Wake", "validate_code"]


def validate_code(code: Tuple[str, str]) -> WakeCode:
    """Two-part codes only, lowercase, no secrets-shaped values."""
    if not isinstance(code, tuple) or len(code) != 2:
        raise ValueError("wake code must be a two-part tuple, e.g. ('growth','tick')")
    for part in code:
        if not isinstance(part, str) or not _CODE_PART.match(part):
            raise ValueError(f"bad wake-code part: {part!r}")
    return (code[0], code[1])


@dataclass
class Wake:
    code: WakeCode
    payload: Any
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    woken: List[str] = field(default_factory=list)
    ignored: bool = False


class AttentionBus:
    """The quiet channel. Subscribe, signal, audit."""

    def __init__(self) -> None:
        self._subs: Dict[WakeCode, List[str]] = {}
        self._ledger: List[Wake] = []

    def subscribe(self, code: Tuple[str, str], name: str) -> WakeCode:
        """Register a service's wake code. Returns the validated code."""
        code = validate_code(code)
        names = self._subs.setdefault(code, [])
        if name not in names:
            names.append(name)
        return code

    def unsubscribe(self, code: Tuple[str, str], name: str) -> None:
        code = validate_code(code)
        names = self._subs.get(code, [])
        if name in names:
            names.remove(name)

    def signal(self, code: Tuple[str, str], payload: Any = None) -> List[str]:
        """Wake only the subscribers addressed by this code.

        Returns the names woken. Everyone else stays asleep — that is the
        whole point.
        """
        code = validate_code(code)
        woken = list(self._subs.get(code, []))
        self._ledger.append(Wake(code=code, payload=payload, woken=woken, ignored=not woken))
        return woken

    def audit(self) -> Dict[str, Any]:
        """How attention was spent: signals, matches, and the ignored."""
        per_code: Dict[str, int] = {}
        for wake in self._ledger:
            key = f"{wake.code[0]}:{wake.code[1]}"
            per_code[key] = per_code.get(key, 0) + 1
        matched = sum(1 for w in self._ledger if not w.ignored)
        return {
            "signals": len(self._ledger),
            "matched": matched,
            "ignored": len(self._ledger) - matched,
            "per_code": per_code,
            "subscribers": sum(len(v) for v in self._subs.values()),
        }

    def ledger(self, limit: Optional[int] = None) -> List[Wake]:
        entries = list(self._ledger)
        return entries[-limit:] if limit else entries
