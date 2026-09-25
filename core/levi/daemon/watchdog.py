"""Comms watchdog — barks when Chauncey's communications need his attention.

NOT the cybersecurity watcher. This daemon watches communications only —
LEVI's own comms stores:

* the SOXI return-loop inbox (teaching batches arrived, awaiting verdict);
* the oath maildir inbox (unseen mail in ``new/`` — headers only);
* the companion request box (open user requests).

When something new needs his attention it BARKS: a notice queued into
the herald outbox (``levi.daemon.herald.notify``, source="watchdog",
level "warn"), which the herald then delivers through its configured
sinks (log always; Termux system notification when on his phone).

Explicit non-goals: no security scanning, no policy/consent checks, no
network probing, no intrusion detection — the cyber watchers (sentinel,
watchman, cyberpulse) stay separate and untouched, and this module
never imports them.

Honest limits: SMS texts and phone notifications have no API wired into
LEVI — the watchdog cannot see them and says so plainly. Phone-side
delivery of its barks happens through the herald's TermuxSink, which
reports honestly when ``termux-notification`` is absent.

The watchdog is read-only: it never marks mail seen, never moves
batches, never closes requests. It counts and points; the human acts.

stdlib-only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import message_from_bytes
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEFAULT_INTERVAL_MIN = 15
ENV_INTERVAL = "LEVI_WATCHDOG_INTERVAL_MIN"
STATE_NAME = "state.json"
MAX_SEEN_PER_SOURCE = 500
MAX_NOTES = 8

# ---------------------------------------------------------------------------
# invariants (law → guard → prove; tests in tests/test_daemon_watchdog.py)
#
# 1. BARK EXACTLY ONCE — a new comms item barks once; re-running never
#    re-barks it. (Guard: per-source seen-id log. Prove: two runs, one bark.)
# 2. NEVER CRASH — a failing comms source ends the tick with one note, not
#    an exception. (Guard: per-source try/except. Prove: broken source →
#    completed result with a note.)
# 3. NOT CYBER — this module never imports or touches sentinel, watchman,
#    cyberpulse, or any security/policy module. (Guard: no such imports.
#    Prove: test scans the module source for the forbidden names.)
# 4. METADATA ONLY — barks carry sender/subject/count, never message bodies.
#    (Guard: readers extract headers/summaries only. Prove: a mail with a
#    body → bark contains no body text.)
# 5. SILENT IDLE — nothing new means no noise. (Guard: silent flag. Prove:
#    empty sources → silent result.)
# ---------------------------------------------------------------------------


@dataclass
class CommsItem:
    """One thing in a comms source that may need Chauncey's attention."""

    source: str  # source key, e.g. "soxi", "oath", "requests"
    item_id: str  # stable id for dedup
    title: str  # short human summary (metadata only, never a body)
    detail: str = ""  # extra metadata (count, sender, subject)

    def uid(self) -> str:
        return "%s:%s" % (self.source, self.item_id)


@dataclass
class WatchdogResult:
    """Outcome of one watchdog tick."""

    checked_at: str  # UTC ISO-8601 timestamp of the check
    sources_checked: int = 0
    new_items: int = 0
    barked: int = 0
    silent: bool = True
    reason: str = "nothing new"
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# comms sources (read-only; each returns metadata-only CommsItems)
# ---------------------------------------------------------------------------


def _read_soxi_batches() -> List[CommsItem]:
    """SOXI return-loop: arrival batches with no verdict yet."""
    from levi.soxi.return_loop import inbox as soxi_inbox

    items: List[CommsItem] = []
    for rec in soxi_inbox.ready_batches():
        if not isinstance(rec, dict):
            continue
        batch_id = str(rec.get("batch_id") or "unknown")
        items.append(
            CommsItem(
                source="soxi",
                item_id=batch_id,
                title="teaching batch %s arrived — awaiting verdict" % batch_id,
                detail="raw_file=%s bytes=%s"
                % (rec.get("raw_file", "?"), rec.get("bytes", "?")),
            )
        )
    return items


def _read_oath_unseen() -> List[CommsItem]:
    """Oath maildir: messages still in new/ (unseen). Headers only."""
    from levi.oath import inbox as oath_inbox

    items: List[CommsItem] = []
    for key, raw in oath_inbox.iter_maildir():
        if not key.startswith("new/"):
            continue  # cur/ is already seen — not our business
        try:
            msg = message_from_bytes(raw)
            sender = str(msg.get("From", "?")).strip()[:80]
            subject = str(msg.get("Subject", "(no subject)")).strip()[:120]
        except Exception:  # noqa: BLE001 — one bad message never kills the tick
            sender, subject = "?", "(unparseable)"
        items.append(
            CommsItem(
                source="oath",
                item_id=key,
                title="unseen mail: %s" % subject,
                detail="from %s" % sender,
            )
        )
    return items


def _read_open_requests() -> List[CommsItem]:
    """Companion request box: requests still open."""
    from levi.inbox.requests import RequestBox

    items: List[CommsItem] = []
    for req in RequestBox().list(status="open"):
        text = (req.text or "").strip().replace("\n", " ")
        items.append(
            CommsItem(
                source="requests",
                item_id=str(req.id),
                title="open request #%s: %s"
                % (req.id, text[:100] + ("…" if len(text) > 100 else "")),
                detail="opened %s" % (req.ts or "?"),
            )
        )
    return items


SourceReader = Callable[[], List[CommsItem]]

DEFAULT_SOURCES: Dict[str, SourceReader] = {
    "soxi": _read_soxi_batches,
    "oath": _read_oath_unseen,
    "requests": _read_open_requests,
}


def _resolve_interval(interval_min: Optional[int] = None) -> int:
    """Resolve the watchdog interval in minutes.

    An explicit argument must be a genuine integer >= 1 — zero,
    negatives, floats, and bools are rejected rather than silently
    mangled. The env var is untrusted config: garbage or non-positive
    values degrade to the default instead of crashing the watchdog.
    """
    if interval_min is not None:
        if (
            not isinstance(interval_min, int)
            or isinstance(interval_min, bool)
            or interval_min < 1
        ):
            raise ValueError(
                f"invalid watchdog interval {interval_min!r}: must be an "
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


def _watchdog_dir(home: Path) -> Path:
    d = home / ".levi" / "watchdog"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_state(wd_dir: Path) -> Dict[str, Any]:
    path = wd_dir / STATE_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(wd_dir: Path, state: Dict[str, Any]) -> None:
    tmp = wd_dir / (STATE_NAME + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(wd_dir / STATE_NAME)


def _bark(item: CommsItem, queue: Any = None) -> str:
    """Queue one bark for a new comms item. Returns the notice id."""
    from levi.daemon.herald import notify

    body = item.detail
    return notify(
        title="watchdog: %s — %s" % (item.source, item.title),
        body=body,
        level="warn",
        source="watchdog",
        queue=queue,
    )


def run_watchdog(
    home: Optional[Path] = None,
    now: Optional[datetime] = None,  # noqa: ARG001 — reserved for cadence tests
    force: bool = False,
    *,
    interval_min: Optional[int] = None,
    queue: Any = None,
    sources: Optional[Dict[str, SourceReader]] = None,
) -> WatchdogResult:
    """Run one watchdog tick over the comms sources.

    ``queue`` injects the herald queue (hermetic tests); ``sources``
    injects the source readers (hermetic tests). Defaults watch the real
    LEVI comms stores and bark into the real herald queue.
    """
    home = Path(home) if home is not None else Path.home()
    checked_at = datetime.now(timezone.utc).isoformat()
    notes: List[str] = []

    wd_dir = _watchdog_dir(home)
    interval = _resolve_interval(interval_min)
    state = _load_state(wd_dir)
    last_run_ts = _parse_ts(state.get("last_run"))
    utc_now = datetime.now(timezone.utc)

    # 1. Interval gate: no-op if the last tick is still fresh.
    if not force and last_run_ts is not None:
        elapsed = (utc_now - last_run_ts).total_seconds()
        if elapsed < interval * 60:
            return WatchdogResult(
                checked_at=checked_at,
                silent=True,
                reason="interval not elapsed",
            )

    seen = state.get("seen") or {}
    if not isinstance(seen, dict):
        seen = {}
    readers = sources if sources is not None else DEFAULT_SOURCES

    sources_checked = new_items = barked = 0

    # 2. Probe each source — one failure never crashes the tick.
    for name, reader in readers.items():
        try:
            items = reader()
        except Exception as exc:  # noqa: BLE001 — report, never crash
            notes.append(
                "watchdog: source '%s' failed (%s: %s)"
                % (name, type(exc).__name__, exc)
            )
            continue
        if not isinstance(items, list):
            notes.append("watchdog: source '%s' returned non-list" % name)
            continue
        sources_checked += 1
        known = set(seen.get(name) or [])
        for item in items:
            if not isinstance(item, CommsItem):
                continue
            if item.item_id in known:
                continue
            new_items += 1
            try:
                _bark(item, queue=queue)
                barked += 1
            except Exception as exc:  # noqa: BLE001
                notes.append(
                    "watchdog: bark for '%s' failed (%s: %s)"
                    % (item.title, type(exc).__name__, exc)
                )
                continue
            known.add(item.item_id)
        seen[name] = sorted(known)[-MAX_SEEN_PER_SOURCE:]

    silent = not (new_items or barked or notes)
    reason = (
        "nothing new"
        if silent
        else "%d new item(s), %d bark(s)" % (new_items, barked)
    )
    result = WatchdogResult(
        checked_at=checked_at,
        sources_checked=sources_checked,
        new_items=new_items,
        barked=barked,
        silent=silent,
        reason=reason,
        notes=notes[:MAX_NOTES],
    )

    state["last_run"] = checked_at
    state["interval_min"] = interval
    state["seen"] = seen
    state["last_counts"] = {
        "sources_checked": sources_checked,
        "new_items": new_items,
        "barked": barked,
    }
    _save_state(wd_dir, state)
    return result


def check(home: Optional[Path] = None) -> "tuple[bool, str]":
    """Supervisor health check: one guarded tick, report what it found."""
    result = run_watchdog(home=home, force=False)
    if result.silent:
        return True, "comms watchdog silent: %s" % result.reason
    return True, "comms watchdog: %s" % result.reason


# ---------------------------------------------------------------------------
# CLI entry (wired by parent into core/levi/cli/main.py)
# ---------------------------------------------------------------------------


def cmd_watchdog(args) -> None:
    """``levi watchdog [run|status]`` — tick the comms watchdog or show state."""
    action = getattr(args, "watchdog_action", "run") or "run"
    if action == "status":
        home = Path.home()
        wd_dir = home / ".levi" / "watchdog"
        state = _load_state(wd_dir)
        interval = _resolve_interval(getattr(args, "interval_min", None))
        counts = state.get("last_counts") or {}
        print("comms watchdog status")
        print("  last run:   %s" % (state.get("last_run") or "never"))
        print(
            "  interval:   %d min%s"
            % (
                interval,
                " (env %s)" % ENV_INTERVAL if os.environ.get(ENV_INTERVAL) else "",
            )
        )
        print("  sources:    %s" % ", ".join(sorted(DEFAULT_SOURCES)))
        print("  new items:  %s" % counts.get("new_items", "n/a"))
        print("  barked:     %s" % counts.get("barked", "n/a"))
        print("  state:      %s" % (wd_dir / STATE_NAME))
        return
    if action == "run":
        result = run_watchdog(
            force=bool(getattr(args, "force", False)),
            interval_min=getattr(args, "interval_min", None),
        )
        if result.silent:
            print("watchdog: quiet (%s)" % result.reason)
        else:
            print(
                "watchdog: %s%s"
                % (
                    result.reason,
                    (" — notes: " + "; ".join(result.notes)) if result.notes else "",
                )
            )
        return
    raise SystemExit("unknown watchdog action: %r (use run|status)" % action)
