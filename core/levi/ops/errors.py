"""Production error surface — structured, never silent on critical paths."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime, timezone


@dataclass
class LeviError:
    code: str
    message: str
    recoverable: bool = True
    detail: Dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def format(self) -> str:
        flag = "recoverable" if self.recoverable else "FATAL"
        return f"[LEVI:{self.code}] ({flag}) {self.message}"


class PersistError(Exception):
    """State write failed after retries."""


class GateError(Exception):
    """HITL / estop blocked action."""


def safe_call(label: str, fn, default=None, log: Optional[list] = None):
    """Run fn; on failure return default and optionally append LeviError to log."""
    try:
        return fn()
    except Exception as e:
        err = LeviError(code=label, message=str(e)[:200], recoverable=True)
        if log is not None:
            log.append(err)
        return default
