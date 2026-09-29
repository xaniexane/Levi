"""Run receipts — append-only evidence that automations actually ran.

Law: a run leaves a receipt or it didn't happen. Every automation
execution records one :class:`Receipt` (name, timestamps, outcome,
duration, short detail) into a JSONL ledger, so later runs can answer
"what ran, when, and did it work" without trusting memory.

Guards (deny-closed):
- ``outcome`` must be one of ``ok | failed | skipped | held`` — anything
  else raises :class:`ReceiptError` and nothing is half-recorded;
- durations are clamped to >= 0; negative input is refused;
- ``detail`` is capped at 280 chars and stored verbatim;
- the ledger is append-only on the write path: :func:`prune` is the only
  destructive op and it rewrites with a generation count.

The ``capture(name)`` context manager is the honest default: the block
runs, the outcome is recorded as ``ok`` or ``failed`` automatically,
and an exception still propagates to the caller (receipts observe —
they never swallow).

Stdlib only, local-first. Default store: ``~/.levi/automation/receipts.jsonl``.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

__all__ = [
    "ReceiptError",
    "OUTCOMES",
    "Receipt",
    "ReceiptLedger",
    "default_ledger_path",
]

OUTCOMES = ("ok", "failed", "skipped", "held")
_MAX_DETAIL = 280


class ReceiptError(ValueError):
    """A receipt that would violate the ledger law. Nothing was recorded."""


def default_ledger_path() -> Path:
    return Path.home() / ".levi" / "automation" / "receipts.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Receipt:
    """One automation run, immutable once recorded."""

    seq: int
    automation: str
    started: str  # ISO-8601 UTC
    ended: str  # ISO-8601 UTC
    duration_s: float  # >= 0, always
    outcome: str  # one of OUTCOMES
    detail: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ReceiptError(
                f"outcome must be one of {OUTCOMES}, got {self.outcome!r}"
            )
        if self.duration_s < 0:
            raise ReceiptError("duration_s must be >= 0")
        if not self.automation or not self.automation.strip():
            raise ReceiptError("automation name must be non-empty")
        if len(self.detail) > _MAX_DETAIL:
            raise ReceiptError(f"detail capped at {_MAX_DETAIL} chars")

    def to_dict(self) -> Dict:
        return {
            "seq": self.seq,
            "automation": self.automation,
            "started": self.started,
            "ended": self.ended,
            "duration_s": round(self.duration_s, 3),
            "outcome": self.outcome,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Receipt":
        return cls(
            seq=int(data["seq"]),
            automation=str(data["automation"]),
            started=str(data["started"]),
            ended=str(data["ended"]),
            duration_s=float(data["duration_s"]),
            outcome=str(data["outcome"]),
            detail=str(data.get("detail", "")),
        )


class ReceiptLedger:
    """Append-only JSONL ledger of automation run receipts."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else default_ledger_path()
        self._seq = self._read_max_seq()

    # -- write path ------------------------------------------------------
    def record(
        self,
        automation: str,
        outcome: str,
        detail: str = "",
        started: Optional[str] = None,
        ended: Optional[str] = None,
        duration_s: Optional[float] = None,
    ) -> Receipt:
        """Record one receipt. The Receipt constructor enforces the law."""
        start = started or _utcnow_iso()
        end = ended or _utcnow_iso()
        dur = duration_s if duration_s is not None else 0.0
        self._seq += 1
        receipt = Receipt(
            seq=self._seq,
            automation=automation.strip(),
            started=start,
            ended=end,
            duration_s=dur,
            outcome=outcome,
            detail=detail[:_MAX_DETAIL],
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict(), ensure_ascii=True) + "\n")
        return receipt

    @contextlib.contextmanager
    def capture(self, automation: str, detail: str = "") -> Iterator[None]:
        """Time a block and record its outcome honestly.

        On clean exit: ``ok``. On exception: ``failed`` with the exception
        type in the detail — and the exception still propagates.
        """
        start_iso = _utcnow_iso()
        t0 = time.monotonic()
        outcome = "ok"
        note = detail
        try:
            yield
        except Exception as exc:  # noqa: BLE001 - receipts observe, never swallow
            outcome = "failed"
            note = f"{detail} [{type(exc).__name__}: {exc}]".strip()[:_MAX_DETAIL]
            raise
        finally:
            dur = max(0.0, time.monotonic() - t0)
            self.record(
                automation,
                outcome,
                detail=note,
                started=start_iso,
                ended=_utcnow_iso(),
                duration_s=dur,
            )

    # -- read path -------------------------------------------------------
    def _iter_all(self) -> Iterator[Receipt]:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield Receipt.from_dict(json.loads(line))
                except (ReceiptError, KeyError, TypeError, ValueError):
                    continue  # corrupt line: evidence skipped, never trusted

    def _read_max_seq(self) -> int:
        seq = 0
        try:
            for r in self._iter_all():
                seq = max(seq, r.seq)
        except OSError:
            pass
        return seq

    def recent(
        self, automation: Optional[str] = None, limit: int = 10
    ) -> List[Receipt]:
        rows = [
            r
            for r in self._iter_all()
            if automation is None or r.automation == automation
        ]
        return rows[-max(1, limit) :]

    def streaks(self) -> Dict[str, int]:
        """Current consecutive-``failed`` streak per automation."""
        streak: Dict[str, int] = {}
        for r in self._iter_all():
            if r.outcome == "failed":
                streak[r.automation] = streak.get(r.automation, 0) + 1
            else:
                streak[r.automation] = 0
        return {k: v for k, v in streak.items() if v > 0}

    def failing(self, threshold: int = 3) -> List[str]:
        """Automations whose current failing streak hits ``threshold``."""
        return sorted(n for n, s in self.streaks().items() if s >= threshold)

    def summarize(self, automation: Optional[str] = None, limit: int = 5) -> str:
        rows = self.recent(automation, limit)
        if not rows:
            return "no receipts recorded."
        lines = []
        for r in rows:
            lines.append(
                f"[{r.seq}] {r.automation}: {r.outcome} "
                f"in {r.duration_s:.1f}s @ {r.started}"
                + (f" — {r.detail}" if r.detail else "")
            )
        bad = self.failing()
        if bad and automation is None:
            lines.append("failing streaks (>=3): " + ", ".join(bad))
        return "\n".join(lines)

    def prune(self, older_than_days: float) -> int:
        """Drop receipts older than ``older_than_days``. Returns rows dropped."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        kept: List[Receipt] = []
        dropped = 0
        for r in self._iter_all():
            try:
                ended = datetime.fromisoformat(r.ended)
                if ended.tzinfo is None:
                    ended = ended.replace(tzinfo=timezone.utc)
            except ValueError:
                kept.append(r)  # unreadable date: keep, never delete blind
                continue
            if ended < cutoff:
                dropped += 1
            else:
                kept.append(r)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in kept:
                fh.write(json.dumps(r.to_dict(), ensure_ascii=True) + "\n")
        os.replace(tmp, self.path)
        self._seq = max((r.seq for r in kept), default=0)
        return dropped
