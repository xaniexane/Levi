"""Adapters: wire the signal plane into the daemon layer.

This module adapts — it never rewrites. ``supervise_once()`` findings and
``HeartbeatResult`` objects are mapped to graded :class:`Signal`s and run
through the single delivery pipeline (focus-mute → active-hours gate →
grade routing). Nothing here forks threads, binds ports, or touches the
network.

Wired instincts (evidence-triggered, never vibes):

* ``instinct.two_miss``    — ``commitments.missed>=2`` → ESCALATE, 24h cooldown
* ``instinct.empty_block`` — ``focus.empty_block`` → CARD, 50m cooldown
* ``instinct.error_spike`` — ``logs.error_spike`` → CARD, 1h cooldown

Evidence contract (all under the LEVI state home, resolved at call time):

* commitments: ``<home>/commitments/commitments.json`` (via the real
  :class:`levi.commitments.commitments.CommitmentStore`)
* agent logs: ``<home>/agent/sessions/*.jsonl`` (error records counted
  over trailing 1h / 24h windows)
* focus blocks: ``<home>/focus/blocks.json`` — a list of
  ``{"name", "start", "end"}`` with ISO datetimes (naive = local).
  Absent file → no focus evidence → the instinct stays silent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.signals.focus import Mode, get_mode, should_deliver as _focus_delivers
from levi.signals.grades import Signal, SignalGrade, render, route
from levi.signals.hours import ActiveHours, DEFAULT_ACTIVE_HOURS
from levi.signals.instincts import Instinct, InstinctRegistry, levi_home

__all__ = [
    "levi_home",
    "gather_evidence",
    "commitments_missed",
    "error_counts",
    "focus_evidence",
    "default_registry",
    "signals_for_supervisor",
    "deliver",
    "heartbeat_to_signals",
    "graded_digest",
    "pulse_with_signals",
    "ERROR_SPIKE_1H",
    "ERROR_SPIKE_24H",
    "EMPTY_BLOCK_IDLE_MIN",
]

# An error "spike": >=5 error records in the trailing hour, or >=10 in 24h.
ERROR_SPIKE_1H = 5
ERROR_SPIKE_24H = 10
# A focus block counts as "empty" when it has run this long with no work.
EMPTY_BLOCK_IDLE_MIN = 25


# ---------------------------------------------------------------------------
# evidence gatherers (read-only, best-effort, never raise)
# ---------------------------------------------------------------------------


def _local_now(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now().astimezone()
    if now.tzinfo is None:
        return now.astimezone()
    return now.astimezone()


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def commitments_missed(home: Path, as_of: Optional[str] = None) -> int:
    """Total missed commitment periods across all commitments.

    Uses the real commitments store; 0 when the store is absent or
    unreadable (evidence absent → the instinct stays silent).
    """
    try:
        from levi.commitments.commitments import CommitmentStore
    except Exception:  # noqa: BLE001 - optional dependency of the plane
        return 0
    try:
        # The store resolves <base>/.levi/commitments; our home IS the
        # state home, so the user base is its parent in the default layout.
        base = home.parent if home.name == ".levi" else home
        store = CommitmentStore(home=base)
        total = 0
        for entry in store.list():
            name = entry.get("name") if isinstance(entry, dict) else None
            if not name:
                continue
            status = store.status(name, as_of=as_of) if as_of else store.status(name)
            missed = status.get("missed") or []
            total += len(missed)
        return total
    except Exception:  # noqa: BLE001 - evidence gathering never raises
        return 0


def error_counts(home: Path, now: Optional[datetime] = None) -> Tuple[int, int]:
    """(errors in trailing 1h, errors in trailing 24h) from agent sessions."""
    moment = _local_now(now).astimezone(timezone.utc)
    sessions = home / "agent" / "sessions"
    if not sessions.is_dir():
        return 0, 0
    cutoff_1h = moment - timedelta(hours=1)
    cutoff_24h = moment - timedelta(hours=24)
    n1h = n24h = 0
    try:
        files = sorted(sessions.glob("*.jsonl"))[:50]
    except OSError:
        return 0, 0
    for path in files:
        try:
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines[-200:]:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            err = rec.get("error")
            if not (isinstance(err, str) and err.strip()):
                continue
            ts = _parse_ts(rec.get("ts")) or _parse_ts(rec.get("timestamp"))
            if ts is None:
                try:
                    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
            if ts >= cutoff_24h:
                n24h += 1
                if ts >= cutoff_1h:
                    n1h += 1
    return n1h, n24h


def focus_evidence(home: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Focus-block evidence: in a scheduled block? is the block empty?

    Reads ``<home>/focus/blocks.json``. A block is "empty" when it has been
    running >= ``EMPTY_BLOCK_IDLE_MIN`` minutes with no agent-session file
    modified since the block started. No blocks file → all False.
    """
    moment = _local_now(now)
    out: Dict[str, Any] = {
        "focus.in_block": False,
        "focus.block_name": "",
        "focus.empty_block": False,
    }
    blocks_path = home / "focus" / "blocks.json"
    try:
        raw = json.loads(blocks_path.read_text(encoding="utf-8"))
        blocks = raw if isinstance(raw, list) else raw.get("blocks", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return out
    current: Optional[Dict[str, Any]] = None
    for block in blocks:
        if not isinstance(block, dict):
            continue
        start = _parse_ts(block.get("start"))
        end = _parse_ts(block.get("end"))
        if start is None or end is None:
            # Naive ISO datetimes are local time for focus blocks.
            try:
                s_raw, e_raw = block.get("start"), block.get("end")
                start_l = datetime.fromisoformat(s_raw)
                end_l = datetime.fromisoformat(e_raw)
            except (ValueError, TypeError):
                continue
            if start_l.tzinfo is None:
                start_l = start_l.astimezone()
            if end_l.tzinfo is None:
                end_l = end_l.astimezone()
            start, end = start_l, end_l
        if start <= moment < end:
            current = block
            current["_start"] = start
            break
    if current is None:
        return out
    out["focus.in_block"] = True
    out["focus.block_name"] = str(current.get("name") or "focus block")
    start = current["_start"]
    elapsed_min = (moment - start).total_seconds() / 60
    if elapsed_min < EMPTY_BLOCK_IDLE_MIN:
        return out
    # Activity probe: any agent-session file touched since the block began?
    active = False
    sessions = home / "agent" / "sessions"
    try:
        for path in sessions.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
            except OSError:
                continue
            if mtime >= start:
                active = True
                break
    except OSError:
        pass
    out["focus.empty_block"] = not active
    return out


def gather_evidence(
    home: "str | os.PathLike[str] | None" = None, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Collect the evidence dict the wired instincts evaluate."""
    base = Path(home).expanduser() if home is not None else levi_home()
    moment = _local_now(now)
    evidence: Dict[str, Any] = {}
    evidence["commitments.missed"] = commitments_missed(
        base, as_of=moment.date().isoformat()
    )
    n1h, n24h = error_counts(base, moment)
    evidence["logs.errors_1h"] = n1h
    evidence["logs.errors_24h"] = n24h
    evidence["logs.error_spike"] = n1h >= ERROR_SPIKE_1H or n24h >= ERROR_SPIKE_24H
    evidence.update(focus_evidence(base, moment))
    return evidence


# ---------------------------------------------------------------------------
# wired instincts
# ---------------------------------------------------------------------------


def _two_miss_handler(evidence: Dict[str, Any]) -> Signal:
    missed = int(evidence.get("commitments.missed") or 0)
    return Signal(
        grade=SignalGrade.ESCALATE,
        tag="[warden]",
        title="%d missed commitment periods need a decision" % missed,
        body=(
            "%d commitment period(s) with no check-in recorded. "
            "Quote the original lock: set a new time, or drop it explicitly. "
            "Silence is not a plan." % missed
        ),
        actions=("set new time", "drop explicitly"),
        requires_ack=True,
        source="instinct.two_miss",
    )


def _empty_block_handler(evidence: Dict[str, Any]) -> Signal:
    name = str(evidence.get("focus.block_name") or "focus block")
    return Signal(
        grade=SignalGrade.CARD,
        tag="[sentinel]",
        title="focus block is empty: %s" % name,
        body=(
            "No work recorded since '%s' started. One redirect, then silence: "
            "are you done, stuck, or switching?" % name
        ),
        actions=("done", "stuck", "switch"),
        due_now=True,  # about the current block: pierces focus mute
        source="instinct.empty_block",
    )


def _error_spike_handler(evidence: Dict[str, Any]) -> Signal:
    n1h = int(evidence.get("logs.errors_1h") or 0)
    n24h = int(evidence.get("logs.errors_24h") or 0)
    return Signal(
        grade=SignalGrade.CARD,
        tag="[sentinel]",
        title="error spike in agent logs",
        body="%d error record(s) in the last hour, %d in the last 24h. "
        "Worth a look before it compounds." % (n1h, n24h),
        actions=("review logs", "dismiss"),
        source="instinct.error_spike",
    )


def default_registry(home: "str | os.PathLike[str] | None" = None) -> InstinctRegistry:
    """Registry with the three supervisor-wired instincts."""
    reg = InstinctRegistry(home=home)
    reg.register(
        Instinct(
            id="instinct.two_miss",
            fires_on="commitments.missed>=2",
            cooldown=24 * 3600,
            max_grade=SignalGrade.ESCALATE,
            does="quote the original lock; demand a new time or an explicit drop",
            handler=_two_miss_handler,
            tag="[warden]",
        )
    )
    reg.register(
        Instinct(
            id="instinct.empty_block",
            fires_on="focus.empty_block",
            cooldown=50 * 60,
            max_grade=SignalGrade.CARD,
            does="ask: done | stuck | switch",
            handler=_empty_block_handler,
            tag="[sentinel]",
        )
    )
    reg.register(
        Instinct(
            id="instinct.error_spike",
            fires_on="logs.error_spike",
            cooldown=3600,
            max_grade=SignalGrade.CARD,
            does="surface the spike count and suggest a log review",
            handler=_error_spike_handler,
            tag="[sentinel]",
        )
    )
    return reg


# ---------------------------------------------------------------------------
# supervisor adapter
# ---------------------------------------------------------------------------


def signals_for_supervisor(
    report: Dict[str, Any],
    home: "str | os.PathLike[str] | None" = None,
    now: Optional[datetime] = None,
) -> List[Signal]:
    """Map ``supervise_once()`` findings to graded signals.

    Down services become CARDs; the wired instincts evaluate live evidence
    on top. Returned highest grade first (stable).
    """
    signals: List[Signal] = []
    services = report.get("services") or {}
    for name, status in services.items():
        if isinstance(status, dict) and not status.get("ok", True):
            signals.append(
                Signal(
                    grade=SignalGrade.CARD,
                    tag="[supervisor]",
                    title="service down: %s" % name,
                    body=str(status.get("detail") or "health check failed"),
                    actions=("retry check", "view logs"),
                    source="supervisor",
                )
            )
    signals.extend(default_registry(home=home).evaluate(gather_evidence(home, now)))
    signals.sort(key=lambda s: s.grade.value, reverse=True)
    return signals


# ---------------------------------------------------------------------------
# heartbeat adapter
# ---------------------------------------------------------------------------


def heartbeat_to_signals(result: Any) -> List[Signal]:
    """Map a ``HeartbeatResult`` to graded signals.

    A silent heartbeat maps to exactly one SILENT signal — routing it
    produces no user-visible output, honestly.
    """
    if getattr(result, "silent", True):
        return [
            Signal(
                grade=SignalGrade.SILENT,
                tag="[heartbeat]",
                title="heartbeat quiet",
                body=str(getattr(result, "reason", "")),
                source="heartbeat",
            )
        ]
    signals: List[Signal] = []
    current: Optional[Signal] = None
    for item in getattr(result, "attention", []) or []:
        if item.startswith("  •"):
            if current is not None:
                current.body += ("\n" if current.body else "") + item.strip()
            continue
        if current is not None:
            signals.append(current)
        current = Signal(
            grade=SignalGrade.CARD,
            tag="[heartbeat]",
            title=item,
            source="heartbeat",
        )
    if current is not None:
        signals.append(current)
    return signals


def graded_digest(
    result: Any,
    *,
    home: "str | os.PathLike[str] | None" = None,
    mode: "Mode | str | None" = None,
    hours: Optional[ActiveHours] = None,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Format a heartbeat digest through the signal plane.

    Returns ``None`` when nothing survives the pipeline — a SILENT
    heartbeat therefore produces genuinely no user-visible output.
    Non-silent results render as tagged cards.
    """
    signals = heartbeat_to_signals(result)
    delivered = deliver(signals, home=home, mode=mode, hours=hours, now=now)
    if not delivered:
        return None
    lines = ["# LEVI heartbeat — %s" % getattr(result, "checked_at", "")]
    for signal in delivered:
        lines.append("")
        lines.append(render(signal))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# the delivery pipeline
# ---------------------------------------------------------------------------


def deliver(
    signals: List[Signal],
    *,
    home: "str | os.PathLike[str] | None" = None,
    mode: "Mode | str | None" = None,
    hours: Optional[ActiveHours] = None,
    now: Optional[datetime] = None,
) -> List[Signal]:
    """Run signals through focus-mute then the active-hours gate.

    ``mode`` defaults to the persisted mode (``get_mode``). SILENT
    signals are dropped here too — belt and suspenders over ``route()``.
    """
    active_mode = Mode(mode) if mode is not None else get_mode(home)
    gate = hours if hours is not None else DEFAULT_ACTIVE_HOURS
    out: List[Signal] = []
    for signal in signals:
        if signal.grade is SignalGrade.SILENT:
            continue
        if not _focus_delivers(signal, active_mode):
            continue
        if not gate.should_deliver(signal, now):
            continue
        out.append(signal)
    return out


def pulse_with_signals(
    supervisor: Any,
    *,
    home: "str | os.PathLike[str] | None" = None,
    mode: "Mode | str | None" = None,
    hours: Optional[ActiveHours] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """One foreground pulse: supervise, grade, gate, render.

    Takes a ``Supervisor`` instance (adapter — the supervisor is never
    modified). Returns the raw report plus the signals, the delivered
    subset, and their rendered text.
    """
    report = supervisor.supervise_once()
    signals = signals_for_supervisor(report, home=home, now=now)
    delivered = deliver(signals, home=home, mode=mode, hours=hours, now=now)
    rendered = [route(s).render() for s in delivered]
    rendered = [text for text in rendered if text]
    return {
        "report": report,
        "signals": signals,
        "delivered": delivered,
        "rendered": rendered,
    }
