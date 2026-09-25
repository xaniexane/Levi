"""Sentinel — read-only policy/consent watchdog.

LEVI's kernel refuses HIGH/CRITICAL and MEDIUM actions without HITL
(:meth:`levi.daemon.kernel.DaemonKernel.require_permission`), but a
refusal at the gate is not the same as an audit trail. The sentinel
watches the action log (``~/.levi/action_log.jsonl``) and raises a
signalbus alert for every consequential act that went ahead WITHOUT
approval.

Read-only by design: the sentinel never blocks, never modifies, never
deletes. It reports. Blocking stays with the kernel and the human.

An action-log line is JSON shaped::

    {"id": "...", "at": "<iso>", "actor": "...", "action": "...",
     "risk": "LOW|MEDIUM|HIGH|CRITICAL", "approved": true|false,
     "detail": {...}}

Any MEDIUM-or-higher act with ``approved`` not true is a violation.
The sentinel publishes one ``sentinel.policy_violation`` signal per
violation (capped per tick to avoid floods) and keeps a watermark so
each line is judged exactly once.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.sentinel`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.daemon.signalbus import SignalBus

DEFAULT_LOG_PATH = Path.home() / ".levi" / "action_log.jsonl"
DEFAULT_STATE_DIR = Path.home() / ".levi" / "sentinel"

#: Risk levels the sentinel treats as consequential.
CONSEQUENTIAL = {"MEDIUM", "HIGH", "CRITICAL"}

#: Max violation signals per tick — a flood of alerts is itself a failure.
MAX_ALERTS_PER_TICK = 10


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class PolicyViolation:
    action_id: str
    actor: str
    action: str
    risk: str
    at: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SentinelReport:
    """Outcome of one sentinel tick."""

    at: str = ""
    scanned: int = 0
    violations: List[PolicyViolation] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["violations"] = [v.to_dict() for v in self.violations]
        return d


class Sentinel:
    """Read-only watchdog over the action log. Reports; never blocks."""

    def __init__(
        self,
        home: Optional[Path] = None,
        log_path: Optional[Path] = None,
        journal_path: Optional[Path] = None,
    ) -> None:
        self.home = Path(home) if home is not None else Path.home()
        base = self.home / ".levi"
        self.log_path = Path(log_path) if log_path else base / "action_log.jsonl"
        self.state_dir = base / "sentinel"
        self.state_path = self.state_dir / "state.json"
        bus_journal = (
            Path(journal_path) if journal_path else base / "daemon_signalbus.jsonl"
        )
        self.bus = SignalBus(journal_path=bus_journal)

    # -- state ------------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        try:
            _atomic_write(self.state_path, json.dumps(state, indent=2))
        except OSError:
            pass

    # -- judging ----------------------------------------------------------

    @staticmethod
    def _judge(record: Dict[str, Any]) -> Optional[PolicyViolation]:
        """Return a violation if a consequential act lacks approval."""
        if not isinstance(record, dict):
            return None
        risk = str(record.get("risk", "")).upper()
        if risk not in CONSEQUENTIAL:
            return None
        if record.get("approved") is True:
            return None
        return PolicyViolation(
            action_id=str(record.get("id", "?")),
            actor=str(record.get("actor", "?")),
            action=str(record.get("action", "?")),
            risk=risk,
            at=str(record.get("at", "?")),
            reason=(
                f"{risk}-risk act '{record.get('action', '?')}' ran without "
                "approval (sentinel is read-only: reporting, not blocking)"
            ),
        )

    # -- tick --------------------------------------------------------------

    def tick(self) -> SentinelReport:
        """Judge new action-log lines. Never raises; never modifies the log."""
        report = SentinelReport(at=_utcnow_iso())
        state = self._load_state()
        offset = int(state.get("line_offset", 0) or 0)

        try:
            text = self.log_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            state["line_offset"] = 0
            self._save_state(state)
            return report
        except OSError as exc:
            report.errors.append(f"cannot read action log: {exc}")
            return report

        lines = text.splitlines()
        new_lines = lines[offset:]
        report.scanned = len(new_lines)

        alerts = 0
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                report.errors.append("unparseable action-log line skipped")
                continue
            try:
                violation = self._judge(record)
            except Exception as exc:  # noqa: BLE001 — one bad line can't stop us
                report.errors.append(f"judge failed: {exc}")
                continue
            if violation is None:
                continue
            report.violations.append(violation)
            if alerts < MAX_ALERTS_PER_TICK:
                try:
                    self.bus.publish(
                        "sentinel.policy_violation",
                        violation.to_dict(),
                        publisher="sentinel",
                    )
                    alerts += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"bus publish failed: {exc}")

        state["line_offset"] = len(lines)
        state["last_tick"] = report.at
        state["violations_total"] = int(state.get("violations_total", 0) or 0) + len(
            report.violations
        )
        self._save_state(state)
        return report

    def check(self) -> tuple:
        """Lightweight coherence check for the supervisor (never raises)."""
        try:
            state = self._load_state()
            total = int(state.get("violations_total", 0) or 0)
            if self.log_path.exists():
                return True, (
                    f"watching {self.log_path.name}; "
                    f"{total} violation(s) raised to date"
                )
            return True, "sentinel ready (no action log yet)"
        except Exception as exc:  # noqa: BLE001
            return False, f"sentinel check failed: {exc}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.sentinel")
    ap.parse_args(argv)
    report = Sentinel().tick()
    print(
        "sentinel tick: scanned=%d violations=%d"
        % (report.scanned, len(report.violations))
    )
    for v in report.violations:
        print(f"  VIOLATION {v.risk} {v.actor}: {v.action} ({v.action_id})")
    for err in report.errors:
        print(f"  error: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
