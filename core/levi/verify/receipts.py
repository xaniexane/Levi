"""Verification receipts: every check's honest, never-silent outcome.

A check never raises on a *failed* check — failure is the outcome and it is
recorded. It raises only on malformed input (deny-closed API use): a check
that cannot honestly run refuses to pretend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VerificationReceipt:
    """The desk-machine proof slip for one verification."""

    ok: bool
    method: str  # e.g. "cast-out-nines", "crossfoot", "dual-path"
    detail: str  # human-readable: what was checked and what it showed
    expected: Optional[str] = None
    got: Optional[str] = None

    def __str__(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        return "[%s] %s: %s" % (mark, self.method, self.detail)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "method": self.method,
            "detail": self.detail,
            "expected": self.expected,
            "got": self.got,
        }
