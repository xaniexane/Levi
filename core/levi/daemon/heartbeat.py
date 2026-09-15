"""
LEVI autonomous heartbeat — periodic, cheap, offline self-check.

Runs on a fixed interval during active hours (8am-10pm local). It scans
local state for things that need attention:

* growth learnings flagged ``provisional`` (unreviewed) since the last run
  — see ``core/levi/growth/consolidate.py``, stored as memory entries
  tagged ``growth`` in ``~/.levi/memory/index.json``
* pending tracked items — automations in ``~/.levi/automations/``
  that failed their last run, went stale, or are still drafts
* recent errors — agent session records under ``~/.levi/agent/sessions/``
  from the last 24h

When nothing needs attention the heartbeat stays SILENT (one quiet line,
no digest). When something does, it prints a short digest and saves it to
``~/.levi/heartbeat/last_digest.md``.

The heartbeat is deliberately heuristic and read-only: no model/provider
calls, no network. Any single check failing is reported as one attention
item and never crashes the run.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ACTIVE_START_HOUR = 8  # local time, inclusive
ACTIVE_END_HOUR = 22  # local time, exclusive
DEFAULT_INTERVAL_MIN = 30
ENV_INTERVAL = "LEVI_HEARTBEAT_INTERVAL_MIN"
RECENT_ERRORS_HOURS = 24
STALE_AUTOMATION_DAYS = 7
MAX_ITEMS_PER_SOURCE = 5

STATE_NAME = "state.json"
DIGEST_NAME = "last_digest.md"

# --------------------------------------------------------------------------
# study-hall cadence — the growth cycle runs on its own slower clock, but
# ONLY when idle. See levi.growth.study for the honest details.
# --------------------------------------------------------------------------

STUDY_ENV_ENABLED = "LEVI_STUDY_ENABLED"
STUDY_ENV_INTERVAL = "LEVI_STUDY_INTERVAL_HOURS"
STUDY_DEFAULT_INTERVAL_HOURS = 4


@dataclass
class HeartbeatResult:
    """Outcome of one heartbeat run."""

    checked_at: str  # UTC ISO-8601 timestamp of the check
    attention: List[str] = field(default_factory=list)
    silent: bool = True
    reason: str = "nothing needs attention"


# --------------------------------------------------------------------------
# time / interval helpers
# --------------------------------------------------------------------------


def _local_now(now: Optional[datetime] = None) -> datetime:
    """Return an aware datetime in local time (``now`` defaults to real now)."""
    if now is None:
        return datetime.now().astimezone()
    if now.tzinfo is None:
        return now.astimezone()
    return now.astimezone()


def _resolve_interval(interval_min: Optional[int] = None) -> int:
    """Resolve the heartbeat interval in minutes.

    An explicit argument must be a genuine integer >= 1 — zero,
    negatives, floats, and bools are rejected rather than silently
    mangled (a 0-minute interval would spin the daemon hot). The env
    var is untrusted config: garbage or non-positive values degrade
    to the default instead of crashing the heartbeat.
    """
    if interval_min is not None:
        if (
            not isinstance(interval_min, int)
            or isinstance(interval_min, bool)
            or interval_min < 1
        ):
            raise ValueError(
                f"invalid heartbeat interval {interval_min!r}: must be an "
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
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _heartbeat_dir(home: Path) -> Path:
    d = home / ".levi" / "heartbeat"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_state(hb_dir: Path) -> Dict[str, Any]:
    path = hb_dir / STATE_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(hb_dir: Path, state: Dict[str, Any]) -> None:
    tmp = hb_dir / (STATE_NAME + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(hb_dir / STATE_NAME)


# --------------------------------------------------------------------------
# self-check sources (read-only, best-effort; never raise)
# --------------------------------------------------------------------------


def _check_growth_learnings(home: Path, since: datetime) -> List[str]:
    """Provisional growth learnings added since the last heartbeat."""
    items: List[str] = []
    index_path = home / ".levi" / "memory" / "index.json"
    if not index_path.exists():
        return items
    raw = json.loads(index_path.read_text(encoding="utf-8"))
    entries = raw.get("entries", []) if isinstance(raw, dict) else []
    new_learn: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tags = entry.get("tags") or []
        metadata = entry.get("metadata") or {}
        if "growth" not in tags:
            continue
        if metadata.get("status") != "provisional":
            continue
        created = _parse_ts(entry.get("created_at"))
        if created is None or created < since:
            continue
        summary = (entry.get("content") or "").strip().replace("\n", " ")
        new_learn.append(summary[:120] + ("…" if len(summary) > 120 else ""))
    if new_learn:
        items.append(
            "growth: %d provisional learning(s) since last heartbeat — review needed"
            % len(new_learn)
        )
        items.extend("  • " + s for s in new_learn[:MAX_ITEMS_PER_SOURCE])
        if len(new_learn) > MAX_ITEMS_PER_SOURCE:
            items.append("  • +%d more" % (len(new_learn) - MAX_ITEMS_PER_SOURCE))
    return items


def _check_tracked_items(home: Path, now: datetime) -> List[str]:
    """Automations that failed, went stale, or are still drafts."""
    items: List[str] = []
    reg_path = home / ".levi" / "automations" / "automations.json"
    if not reg_path.exists():
        return items
    raw = json.loads(reg_path.read_text(encoding="utf-8"))
    autos = raw.get("automations", []) if isinstance(raw, dict) else []
    stale_cutoff = now.astimezone(timezone.utc) - timedelta(days=STALE_AUTOMATION_DAYS)
    flagged = 0
    for auto in autos:
        if flagged >= MAX_ITEMS_PER_SOURCE or not isinstance(auto, dict):
            continue
        name = auto.get("name") or auto.get("id") or "unnamed"
        status = str(auto.get("status", "")).lower()
        last_run = _parse_ts(auto.get("last_run"))
        last_result = str(auto.get("last_result") or "").lower()
        detail: Optional[str] = None
        if status == "active" and any(
            marker in last_result
            for marker in ("fail", "error", "exception", "timeout")
        ):
            detail = "last run failed"
        elif status == "active" and (last_run is None or last_run < stale_cutoff):
            detail = "stale (no successful run in %d+ days)" % STALE_AUTOMATION_DAYS
        elif status == "draft" and auto.get("actions"):
            detail = "draft with actions configured — not yet active"
        if detail is not None:
            items.append("tracked item: automation '%s' — %s" % (name, detail))
            flagged += 1
    return items


def _check_recent_errors(home: Path, now: datetime) -> List[str]:
    """Errors recorded in agent sessions within the last 24 hours."""
    items: List[str] = []
    sessions_dir = home / ".levi" / "agent" / "sessions"
    if not sessions_dir.is_dir():
        return items
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=RECENT_ERRORS_HOURS)
    flagged: Dict[str, int] = {}
    files = sorted(sessions_dir.glob("*.jsonl"))
    for path in files[:50]:
        try:
            if not path.is_file():
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            count = 0
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
                if isinstance(err, str) and err.strip():
                    rec_ts = _parse_ts(rec.get("ts")) or _parse_ts(rec.get("timestamp"))
                    if rec_ts is None or rec_ts >= cutoff:
                        count += 1
            if count:
                flagged[path.name] = count
        except OSError:
            continue
    total = sum(flagged.values())
    if total:
        items.append(
            "errors: %d error record(s) in agent sessions in the last %dh"
            % (total, RECENT_ERRORS_HOURS)
        )
        for name in list(flagged)[:MAX_ITEMS_PER_SOURCE]:
            items.append("  • %s: %d error(s)" % (name, flagged[name]))
    return items


_CHECKS: List[tuple] = [
    ("growth learnings", _check_growth_learnings),
    ("tracked items", _check_tracked_items),
    ("recent errors", _check_recent_errors),
]


# --------------------------------------------------------------------------
# study-hall cadence
# --------------------------------------------------------------------------


def _study_interval_hours() -> float:
    """Study-hall cadence in hours. The env var is untrusted config:
    garbage, non-finite, or non-positive values degrade to the default
    rather than breaking the study schedule (NaN would silently
    disable the interval gate; 0 would study every run)."""
    try:
        value = float(
            os.environ.get(STUDY_ENV_INTERVAL, "") or STUDY_DEFAULT_INTERVAL_HOURS
        )
    except (TypeError, ValueError):
        return float(STUDY_DEFAULT_INTERVAL_HOURS)
    if not math.isfinite(value) or value <= 0:
        return float(STUDY_DEFAULT_INTERVAL_HOURS)
    return value


def _maybe_run_study(home: Path, state: Dict[str, Any], now_utc: datetime) -> str:
    """Run the study cycle on its own clock, only when idle.

    Never raises: any failure is reported as a note string, never as a
    heartbeat attention item (the study hall is a background habit, not
    an alarm). Returns a short note describing what happened.
    """
    try:
        from levi.growth import study as _study
    except Exception as exc:  # noqa: BLE001
        return "study: skipped (study module unavailable: %s)" % type(exc).__name__

    if not _study.study_enabled():
        return "study: disabled (%s=0)" % STUDY_ENV_ENABLED

    interval = _study_interval_hours()
    last_study = _parse_ts(state.get("last_study"))
    if last_study is not None:
        elapsed = (now_utc - last_study).total_seconds()
        if elapsed < interval * 3600:
            return "study: interval not elapsed"

    # Idle gate — the whole point: never study while Chauncey is around.
    try:
        if not _study.is_idle(home, window_hours=interval):
            return "study: skipped (recent activity — not idle)"
    except Exception as exc:  # noqa: BLE001 — probe failure = stay silent
        return "study: skipped (idle check failed: %s)" % type(exc).__name__

    try:
        report = _study.run_study(use_model=False)  # rules-only: cheap + offline
    except Exception as exc:  # noqa: BLE001
        return "study: failed (%s: %s)" % (type(exc).__name__, exc)

    state["last_study"] = now_utc.isoformat()
    state["study_interval_hours"] = interval
    state["study_runs"] = int(state.get("study_runs", 0) or 0) + 1
    q = report.get("quiz") or {}
    score = q.get("mean_score")
    return "study: ran cycle %s (quiz mean=%s)" % (
        report.get("cycle_id"),
        ("%.2f" % score) if isinstance(score, (int, float)) else "n/a",
    )


# --------------------------------------------------------------------------
# digest formatting
# --------------------------------------------------------------------------


def format_digest(result: HeartbeatResult) -> str:
    lines = ["# LEVI heartbeat — %s" % result.checked_at]
    if result.silent:
        lines.append("")
        lines.append("quiet: %s" % result.reason)
    else:
        lines.append("")
        for item in result.attention:
            if item.startswith("  •"):
                lines.append(item)
            else:
                lines.append("- " + item)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# main entry
# --------------------------------------------------------------------------


def run_heartbeat(
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
    force: bool = False,
    *,
    interval_min: Optional[int] = None,
) -> HeartbeatResult:
    """Run one heartbeat check.

    Silent (cheap, idempotent no-op) when outside active hours or when the
    last run was inside the check interval — unless ``force=True``.
    """
    home = Path(home) if home is not None else Path.home()
    local = _local_now(now)
    now_utc = local.astimezone(timezone.utc)
    checked_at = now_utc.isoformat()

    # 1. Active-hours gate: 8am–10pm local only.
    if not (ACTIVE_START_HOUR <= local.hour < ACTIVE_END_HOUR):
        return HeartbeatResult(
            checked_at=checked_at,
            attention=[],
            silent=True,
            reason="outside active hours",
        )

    hb_dir = _heartbeat_dir(home)
    interval = _resolve_interval(interval_min)
    state = _load_state(hb_dir)
    last_run_ts = _parse_ts(state.get("last_run"))

    # 2. Interval gate: no-op if the last run is still fresh.
    if not force and last_run_ts is not None:
        elapsed = (now_utc - last_run_ts).total_seconds()
        if elapsed < interval * 60:
            return HeartbeatResult(
                checked_at=checked_at,
                attention=[],
                silent=True,
                reason="interval not elapsed",
            )

    since = last_run_ts or (now_utc - timedelta(hours=RECENT_ERRORS_HOURS))

    # 3. Self-checks — each source guarded so one failure can't crash the run.
    attention: List[str] = []
    for label, fn in _CHECKS:
        try:
            if label == "growth learnings":
                attention.extend(fn(home, since))
            else:
                attention.extend(fn(home, local))
        except Exception as exc:  # noqa: BLE001 — report, never crash
            attention.append(
                "heartbeat check '%s' failed (%s): %s"
                % (label, type(exc).__name__, exc)
            )
            if len(attention) > MAX_ITEMS_PER_SOURCE * len(_CHECKS):
                break

    silent = not attention
    reason = (
        "nothing needs attention"
        if silent
        else "%d item(s) need attention"
        % len([a for a in attention if not a.startswith("  •")])
    )
    result = HeartbeatResult(
        checked_at=checked_at, attention=attention, silent=silent, reason=reason
    )

    # 4. Study-hall cadence: own clock, idle-only, never an attention item.
    study_note = _maybe_run_study(home, state, now_utc)

    # 5. Persist state + digest.
    state["last_run"] = checked_at
    state["interval_min"] = interval
    state["last_attention_count"] = len(
        [a for a in attention if not a.startswith("  •")]
    )
    if not silent:
        digest_path = hb_dir / DIGEST_NAME
        digest_path.write_text(format_digest(result), encoding="utf-8")
        state["last_digest"] = str(digest_path)
    state["last_study_note"] = study_note
    _save_state(hb_dir, state)

    return result


# --------------------------------------------------------------------------
# CLI entry (wired by parent into core/levi/cli/main.py)
# --------------------------------------------------------------------------


def cmd_heartbeat(args) -> None:
    """``levi heartbeat [run|status]`` — run the self-check or show state."""
    action = getattr(args, "heartbeat_action", "run") or "run"
    if action == "status":
        home = Path.home()
        hb_dir = home / ".levi" / "heartbeat"
        state = _load_state(hb_dir)
        interval = _resolve_interval(getattr(args, "interval_min", None))
        digest_path = hb_dir / DIGEST_NAME
        count = state.get("last_attention_count")
        if count is None and digest_path.exists():
            try:
                count = sum(
                    1
                    for line in digest_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("- ")
                )
            except OSError:
                count = 0
        print("heartbeat status")
        print("  last run:            %s" % (state.get("last_run") or "never"))
        print(
            "  interval:            %d min%s"
            % (
                interval,
                " (env %s)" % ENV_INTERVAL if os.environ.get(ENV_INTERVAL) else "",
            )
        )
        print(
            "  active hours:        %02d:00–%02d:00 local"
            % (ACTIVE_START_HOUR, ACTIVE_END_HOUR)
        )
        print("  attention items:     %s" % (count if count is not None else "n/a"))
        print("  last study:          %s" % (state.get("last_study") or "never"))
        print("  study note:          %s" % (state.get("last_study_note") or "n/a"))
        print(
            "  study every:         %s h (env %s), idle-gated"
            % (
                os.environ.get(STUDY_ENV_INTERVAL, STUDY_DEFAULT_INTERVAL_HOURS),
                STUDY_ENV_INTERVAL,
            )
        )
        print("  state:               %s" % (hb_dir / STATE_NAME))
        return
    if action == "run":
        result = run_heartbeat(
            force=bool(getattr(args, "force", False)),
            interval_min=getattr(args, "interval_min", None),
        )
        if result.silent:
            print("heartbeat: quiet (%s)" % result.reason)
        else:
            print(format_digest(result), end="")
        return
    raise SystemExit("unknown heartbeat action: %r (use run|status)" % action)
