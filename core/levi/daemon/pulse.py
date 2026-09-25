"""DemandPulse pulse — heartbeat-style daemon for DemandPulse and its alerts.

Distinct from the generic heartbeat (``levi.daemon.heartbeat``): the
pulse beats for DemandPulse only. Each tick it:

1. loads the current DemandPulse state (``levi.demand.pulse.DemandPulse``)
   — signals, opportunities, score cards;
2. evaluates Chauncey's alert definitions against it
   (``levi.demand.alerts.AlertEngine`` — threshold / watch / briefing /
   reminder, with dedup keys and quiet-hours holds);
3. delivers due events through the engine's configured channels, and
   barks every delivered event into the herald queue
   (``levi.daemon.herald.notify``, source="pulse") so Chauncey actually
   hears it;
4. stays SILENT (one quiet line) when nothing fires.

Unlike the generic heartbeat there is no active-hours gate: the pulse
must tick around the clock so threshold crossings are caught when they
happen — delivery itself is held for quiet hours by the alert engine.

The pulse is read-only against DemandPulse state and the alert store —
it executes nothing and touches no money. Any single failure (corrupt
state file, broken alert definition) is reported as one honest pulse
note and never crashes the tick. Push/email channels stay visibly
"not_configured" until Chauncey wires them — the pulse never pretends
a notification reached his phone when it didn't.

stdlib-only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_INTERVAL_MIN = 30
ENV_INTERVAL = "LEVI_PULSE_INTERVAL_MIN"
STATE_NAME = "state.json"
MAX_NOTES = 8

# ---------------------------------------------------------------------------
# invariants (law → guard → prove; tests in tests/test_daemon_pulse.py)
#
# 1. EXACTLY-ONCE FIRING — a due alert fires and barks once; re-running the
#    pulse never re-fires it. (Guard: alert-engine dedup keys + the pulse's
#    own forwarded-key log. Prove: two consecutive runs, one bark.)
# 2. QUIET HOURS HOLD — events fired inside quiet hours are never delivered
#    and never dropped; they flush after quiet hours end. (Guard: the alert
#    engine's held/pending path. Prove: fire during quiet hours → held, not
#    delivered; next run outside quiet hours → flushed.)
# 3. NEVER CRASH — a corrupt DemandPulse state or alert store ends the tick
#    with one honest note, not an exception. (Guard: per-stage try/except.
#    Prove: corrupt JSON → completed result with a note.)
# 4. HONEST CHANNELS — unconfigured channels report "not_configured", never
#    "delivered". (Guard: AlertEngine.deliver. Prove: push/email event →
#    status says not_configured.)
# 5. SILENT IDLE — no firings means no noise. (Guard: silent flag. Prove:
#    empty state → silent result.)
# ---------------------------------------------------------------------------


@dataclass
class PulseResult:
    """Outcome of one pulse tick."""

    checked_at: str  # UTC ISO-8601 timestamp of the check
    fired: int = 0
    delivered: int = 0
    held: int = 0
    flushed: int = 0
    barked: int = 0
    silent: bool = True
    reason: str = "nothing fired"
    notes: List[str] = field(default_factory=list)


def _resolve_interval(interval_min: Optional[int] = None) -> int:
    """Resolve the pulse interval in minutes.

    An explicit argument must be a genuine integer >= 1 — zero,
    negatives, floats, and bools are rejected rather than silently
    mangled (a 0-minute interval would spin the daemon hot). The env
    var is untrusted config: garbage or non-positive values degrade
    to the default instead of crashing the pulse.
    """
    if interval_min is not None:
        if (
            not isinstance(interval_min, int)
            or isinstance(interval_min, bool)
            or interval_min < 1
        ):
            raise ValueError(
                f"invalid pulse interval {interval_min!r}: must be an "
                f"integer >= 1 (minutes)"
            )
        return interval_min
    try:
        value = int(os.environ.get(ENV_INTERVAL, "") or DEFAULT_INTERVAL_MIN)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_MIN
    return value if value >= 1 else DEFAULT_INTERVAL_MIN


def _parse_ts(raw: Any) -> Optional[datetime]:
    """Best-effort parse of an ISO-8601 timestamp → aware UTC datetime."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pulse_dir(home: Path) -> Path:
    d = home / ".levi" / "pulse"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_state(pulse_dir: Path) -> Dict[str, Any]:
    path = pulse_dir / STATE_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(pulse_dir: Path, state: Dict[str, Any]) -> None:
    tmp = pulse_dir / (STATE_NAME + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(pulse_dir / STATE_NAME)


def _precheck_state_file(path: Path) -> None:
    """Raise on a corrupt demand-state file so the tick reports one honest
    note. An absent file is fine (empty state); a corrupt one is not —
    ``DemandPulse._load`` would only warn to stderr and continue empty,
    which is too quiet for a daemon whose whole job is noticing."""
    p = Path(path)
    if not p.exists():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("unreadable demand state (%s)" % exc) from exc
    if not isinstance(raw, dict):
        raise ValueError("demand state top level is not an object")


def _bark_level(kind: str) -> str:
    return "warn" if kind in ("threshold", "watch") else "info"


def _bark(event: Any, queue: Any = None) -> str:
    """Queue one bark for a delivered alert event. Returns the notice id."""
    from levi.daemon.herald import notify

    body = "\n".join("• " + line for line in (event.lines or []))
    return notify(
        title="pulse: %s" % event.title,
        body="%s\n\n(%s — %s)" % (body, event.alert_name, event.kind),
        level=_bark_level(event.kind),
        source="pulse",
        queue=queue,
    )


def run_pulse(
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
    force: bool = False,
    *,
    interval_min: Optional[int] = None,
    dp_path: Optional[Path] = None,
    alerts_path: Optional[Path] = None,
    queue: Any = None,
) -> PulseResult:
    """Run one pulse tick over DemandPulse alerts.

    ``dp_path`` / ``alerts_path`` / ``queue`` are injectable for hermetic
    tests; they default to the live DemandPulse state, the live alert
    store, and the live herald queue.
    """
    from levi.demand.alerts import AlertEngine, _now_local
    from levi.demand.pulse import DEFAULT as _DP_DEFAULT
    from levi.demand.pulse import DemandPulse

    home = Path(home) if home is not None else Path.home()
    checked_at = datetime.now(timezone.utc).isoformat()
    notes: List[str] = []

    pulse_dir = _pulse_dir(home)
    interval = _resolve_interval(interval_min)
    state = _load_state(pulse_dir)
    last_run_ts = _parse_ts(state.get("last_run"))
    utc_now = datetime.now(timezone.utc)

    # 1. Interval gate: no-op if the last tick is still fresh.
    if not force and last_run_ts is not None:
        elapsed = (utc_now - last_run_ts).total_seconds()
        if elapsed < interval * 60:
            return PulseResult(
                checked_at=checked_at,
                silent=True,
                reason="interval not elapsed",
            )

    # 2. Load DemandPulse state — corrupt store ends the tick with a note.
    try:
        _precheck_state_file(Path(dp_path) if dp_path else _DP_DEFAULT)
        dp = DemandPulse(path=dp_path) if dp_path else DemandPulse()
    except Exception as exc:  # noqa: BLE001 — report, never crash
        note = "pulse: could not load DemandPulse state (%s: %s)" % (
            type(exc).__name__,
            exc,
        )
        return PulseResult(
            checked_at=checked_at, silent=True, reason="state unreadable",
            notes=[note],
        )

    # 3. Load the alert engine — same honesty contract.
    try:
        engine = AlertEngine(path=alerts_path) if alerts_path else AlertEngine()
    except Exception as exc:  # noqa: BLE001
        note = "pulse: could not load alert store (%s: %s)" % (
            type(exc).__name__,
            exc,
        )
        return PulseResult(
            checked_at=checked_at, silent=True, reason="alert store unreadable",
            notes=[note],
        )

    local_now = now or _now_local()
    forwarded = state.get("forwarded_keys") or {}
    if not isinstance(forwarded, dict):
        forwarded = {}

    fired = delivered = held = flushed = barked = 0

    # 4. Evaluate — each due event is delivered or held by the engine.
    try:
        events = engine.evaluate(dp, local_now)
    except Exception as exc:  # noqa: BLE001
        notes.append(
            "pulse: alert evaluation failed (%s: %s)" % (type(exc).__name__, exc)
        )
        events = []
    fired = len(events)

    for event in events:
        if event.held:
            engine.pending.append(event.to_dict())
            held += 1
            continue
        try:
            status = engine.deliver(event)
        except Exception as exc:  # noqa: BLE001
            notes.append(
                "pulse: delivery of '%s' failed (%s: %s)"
                % (event.title, type(exc).__name__, exc)
            )
            continue
        delivered += 1
        for ch, st in status.items():
            if st == "not_configured":
                notes.append(
                    "pulse: '%s' — channel '%s' not configured; console/file copy kept"
                    % (event.title, ch)
                )
        # Bark into the herald queue — exactly once per dedup key.
        if event.dedup_key not in forwarded:
            try:
                _bark(event, queue=queue)
                forwarded[event.dedup_key] = checked_at
                barked += 1
            except Exception as exc:  # noqa: BLE001
                notes.append(
                    "pulse: bark for '%s' failed (%s: %s)"
                    % (event.title, type(exc).__name__, exc)
                )

    # Held events were appended after evaluate()'s persist — save them now
    # so a later tick can flush them once quiet hours end.
    if held:
        try:
            engine._persist()
        except Exception as exc:  # noqa: BLE001
            notes.append(
                "pulse: could not persist held events (%s: %s)"
                % (type(exc).__name__, exc)
            )

    # 5. Flush events held through quiet hours, now that it may be over.
    try:
        still_pending: List[Dict[str, Any]] = []
        for raw in engine.pending:
            alert = engine.get(raw.get("alert_id", ""))
            if alert and not _in_quiet(alert, local_now):
                from levi.demand.alerts import AlertEvent

                event = AlertEvent(
                    **{
                        k: v
                        for k, v in raw.items()
                        if k in AlertEvent.__dataclass_fields__
                    }
                )
                event.held = False
                try:
                    engine.deliver(event)
                except Exception as exc:  # noqa: BLE001
                    notes.append(
                        "pulse: flush delivery of '%s' failed (%s: %s)"
                        % (event.title, type(exc).__name__, exc)
                    )
                    still_pending.append(raw)
                    continue
                flushed += 1
                if event.dedup_key not in forwarded:
                    try:
                        _bark(event, queue=queue)
                        forwarded[event.dedup_key] = checked_at
                        barked += 1
                    except Exception as exc:  # noqa: BLE001
                        notes.append(
                            "pulse: bark for flushed '%s' failed (%s: %s)"
                            % (event.title, type(exc).__name__, exc)
                        )
            else:
                still_pending.append(raw)
        if len(still_pending) != len(engine.pending):
            engine.pending = still_pending
            engine._persist()
    except Exception as exc:  # noqa: BLE001
        notes.append("pulse: quiet-hours flush failed (%s: %s)"
                     % (type(exc).__name__, exc))

    silent = not (fired or delivered or held or flushed or notes)
    reason = (
        "nothing fired"
        if silent
        else "%d fired (%d delivered, %d held, %d flushed)"
        % (fired, delivered, held, flushed)
    )
    result = PulseResult(
        checked_at=checked_at,
        fired=fired,
        delivered=delivered,
        held=held,
        flushed=flushed,
        barked=barked,
        silent=silent,
        reason=reason,
        notes=notes[:MAX_NOTES],
    )

    state["last_run"] = checked_at
    state["interval_min"] = interval
    state["forwarded_keys"] = dict(list(forwarded.items())[-500:])
    state["last_counts"] = {
        "fired": fired,
        "delivered": delivered,
        "held": held,
        "flushed": flushed,
        "barked": barked,
    }
    _save_state(pulse_dir, state)
    return result


def _in_quiet(alert: Any, now: datetime) -> bool:
    from levi.demand.alerts import in_quiet_hours

    return in_quiet_hours(now, alert.quiet_start, alert.quiet_end)


def check(home: Optional[Path] = None) -> "tuple[bool, str]":
    """Supervisor health check: one guarded tick, report what it found."""
    result = run_pulse(home=home, force=False)
    if result.silent:
        return True, "demand pulse silent: %s" % result.reason
    return True, "demand pulse: %s" % result.reason


# ---------------------------------------------------------------------------
# CLI entry (wired by parent into core/levi/cli/main.py)
# ---------------------------------------------------------------------------


def cmd_pulse(args) -> None:
    """``levi pulse [run|status]`` — tick the DemandPulse alerts or show state."""
    action = getattr(args, "pulse_action", "run") or "run"
    if action == "status":
        home = Path.home()
        pulse_dir = home / ".levi" / "pulse"
        state = _load_state(pulse_dir)
        interval = _resolve_interval(getattr(args, "interval_min", None))
        counts = state.get("last_counts") or {}
        print("demand pulse status")
        print("  last run:    %s" % (state.get("last_run") or "never"))
        print(
            "  interval:    %d min%s"
            % (
                interval,
                " (env %s)" % ENV_INTERVAL if os.environ.get(ENV_INTERVAL) else "",
            )
        )
        print("  last fired:  %s" % counts.get("fired", "n/a"))
        print("  delivered:   %s" % counts.get("delivered", "n/a"))
        print("  held:        %s" % counts.get("held", "n/a"))
        print("  flushed:     %s" % counts.get("flushed", "n/a"))
        print("  barked:      %s" % counts.get("barked", "n/a"))
        print("  state:       %s" % (pulse_dir / STATE_NAME))
        return
    if action == "run":
        result = run_pulse(
            force=bool(getattr(args, "force", False)),
            interval_min=getattr(args, "interval_min", None),
        )
        if result.silent:
            print("pulse: quiet (%s)" % result.reason)
        else:
            print(
                "pulse: %s%s"
                % (
                    result.reason,
                    (" — notes: " + "; ".join(result.notes)) if result.notes else "",
                )
            )
        return
    raise SystemExit("unknown pulse action: %r (use run|status)" % action)
