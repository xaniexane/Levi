"""DemandPulse alerts — Copilot-style proactive notifications for the sensing skin.

Four alert kinds, mirroring the mechanics Copilot described for its own alerts:
  - threshold: event-driven. Fires when a ScoreCard composite crosses the alert
    threshold or an Opportunity's worth crosses a configured bar. (Copilot's
    "signal listeners that fired when external data changed".)
  - briefing: scheduled, recurring digest of new signals, top opportunities,
    and above-threshold score cards. (Copilot's daily briefing.)
  - watch: segment listener. Fires when a new demand signal lands in a watched
    segment. (Copilot's opt-in opportunity alerts.)
  - reminder: time-based one-shot or recurring nudge. (Copilot's reminders.)

Copilot's rules, kept as law here:
  - Nothing fires unsolicited: every alert is created explicitly, and any
    alert can be listed, deleted, or disabled at any time.
  - Dedup: the same item never fires twice for the same alert. Briefings fire
    at most once per period; reminders fire once per scheduled slot.
  - Quiet hours hold delivery instead of dropping it; held alerts flush on the
    next run outside quiet hours.
  - Delivery channels: console card + file outbox work today. SMS sends for
    real via the Pulse device alerter path (termux-sms-send) when
    LEVI_ALERT_NUMBER is set and the binary exists; email sends for real
    via stdlib SMTP when the LEVI_SMTP_* credentials are set. WhatsApp is
    gated until the WhatsApp side-chat relay task exists (or a WhatsApp
    API endpoint is configured) — it reports the exact setup step, never
    "delivered". "webhook" POSTs the alert JSON to LEVI_ALERT_WEBHOOK_URL
    (fully local — a receiver on his own network works, no services);
    "sheets" POSTs it to LEVI_SHEETS_WEBHOOK_URL (his Google Apps Script
    URL, not supplied yet — reports "unconfigured" naming the var and
    skips cleanly). Push routes through the NeighborOS notifier when one is
    attached to `deliver`/`run` — app_push (the scheduled run's final
    message reaches his phone as push when the app is closed; poll-based,
    not instant) plus any operator-configured webhook targets; without a
    notifier push stays "not_configured".
  - Failover: `AlertEngine.deliver_failover` runs the sms -> email ->
    whatsapp -> webhook -> sheets chain from levi.demand.failover — one
    pipeline fails, the alert goes to the next. Every dispatch is
    chain-logged; "delivered" is only ever reported on downstream
    confirmation.

Honesty contract (inherited from the demand module): alert bodies carry the
HYPOTHESIS / INFERENCE / OBSERVED labels of their source items. An alert
describes an assessment; it executes nothing and touches no money.

stdlib-only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ALERT_TYPES: Tuple[str, ...] = ("threshold", "briefing", "watch", "reminder")
CHANNELS: Tuple[str, ...] = ("console", "file", "push", "email", "sms", "whatsapp", "webhook", "sheets")
# channels served by the failover chain (levi.demand.failover)
FAILOVER_CHANNELS: Tuple[str, ...] = ("sms", "email", "whatsapp", "webhook", "sheets")
RECURRENCE: Tuple[str, ...] = ("once", "daily", "weekly", "monthly")

DEFAULT_ALERTS_PATH = Path.home() / ".levi" / "demand_alerts.json"
DEFAULT_OUTBOX_PATH = Path.home() / ".levi" / "demand_alerts_outbox.jsonl"
DEFAULT_QUIET_START = "22:00"
DEFAULT_QUIET_END = "07:00"

# "Local" for every alert schedule (quiet hours, briefing time, reminders)
# means the user's timezone, not the machine's. The machine may run UTC;
# without this anchor the 07:00 briefing fires at 02:00 user time.
DEFAULT_TIMEZONE = "America/Chicago"
TIMEZONES_FILE = Path.home() / "workspace" / "user" / "timezones.yaml"


def _resolve_timezone() -> str:
    """User's timezone name. Precedence: LEVI_TZ env > timezones.yaml
    home_tz > DEFAULT_TIMEZONE. Invalid names fall back to the default
    rather than crashing the unattended sweep."""
    candidates = []
    env_tz = os.environ.get("LEVI_TZ", "").strip()
    if env_tz:
        candidates.append(env_tz)
    try:
        for line in TIMEZONES_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("home_tz:"):
                file_tz = stripped.split(":", 1)[1].strip().strip("'\"")
                if file_tz:
                    candidates.append(file_tz)
                break
    except OSError:
        pass
    candidates.append(DEFAULT_TIMEZONE)
    for name in candidates:
        try:
            ZoneInfo(name)
        except ZoneInfoNotFoundError:
            continue
        return name
    return "UTC"


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(_resolve_timezone()))


def _parse_hhmm(value: str, name: str) -> Tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be 'HH:MM', got {value!r}")
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"{name} must be 'HH:MM', got {value!r}")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"{name} must be 'HH:MM', got {value!r}") from None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"{name} must be 'HH:MM', got {value!r}")
    return hh, mm


def in_quiet_hours(now: datetime, quiet_start: str, quiet_end: str) -> bool:
    """True when ``now`` falls inside the quiet window.

    A window like 22:00→07:00 wraps midnight; a window like 01:00→05:00
    does not. Equal start/end means "never quiet".
    """
    sh, sm = _parse_hhmm(quiet_start, "quiet_start")
    eh, em = _parse_hhmm(quiet_end, "quiet_end")
    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def _summarize_send(per_backend: Dict[str, str]) -> str:
    """One honest channel status for a multi-backend notifier send."""
    vals = set(per_backend.values())
    for s in (
        "delivered",
        "queued_for_app_push",
        "needs_whatsapp_chat_setup",
        "already_sent",
        "no_targets_configured",
    ):
        if s in vals:
            return s
    if any(str(v).startswith("failed") for v in vals):
        return "failed"
    return "failed"


# Backends that can actually reach the phone. The "push" alert channel
# summarizes ONLY these — local file/console delivery must never make a
# push channel report "delivered".
PUSH_BACKENDS = ("app_push", "webhook", "whatsapp")


@dataclass(frozen=True)
class Alert:
    """One user-created alert definition."""

    id: str
    type: str  # one of ALERT_TYPES
    name: str
    enabled: bool = True
    # schedule (briefing + recurring reminder)
    time: str = "07:00"  # HH:MM in the anchored user timezone (see _now_local)
    recurrence: str = "daily"  # once | daily | weekly | monthly
    at: str = ""  # ISO datetime in the anchored user timezone, for one-shot reminders
    dow: int = -1  # weekly only: 0=Monday..6=Sunday, -1 = any day
    # triggers
    threshold: float = 75.0  # score-card composite bar (0-100)
    worth_bar: float = 0.80  # opportunity worth bar (0-1)
    segment: str = ""  # watched segment (watch alerts)
    message: str = ""  # reminder text
    # delivery
    channels: Tuple[str, ...] = ("console", "file")
    quiet_start: str = DEFAULT_QUIET_START
    quiet_end: str = DEFAULT_QUIET_END
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(f"alert id must be a non-empty string, got {self.id!r}")
        if self.type not in ALERT_TYPES:
            raise ValueError(
                f"alert type must be one of {ALERT_TYPES}, got {self.type!r}"
            )
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("alert name must be a non-empty string")
        if not isinstance(self.enabled, bool):
            raise ValueError(f"enabled must be bool, got {self.enabled!r}")
        _parse_hhmm(self.time, "time")
        if self.recurrence not in RECURRENCE:
            raise ValueError(
                f"recurrence must be one of {RECURRENCE}, got {self.recurrence!r}"
            )
        if self.type == "reminder" and self.recurrence == "once":
            if not self.at:
                raise ValueError("one-shot reminders need 'at' (ISO datetime)")
            try:
                datetime.fromisoformat(self.at)
            except ValueError:
                raise ValueError(
                    f"'at' must be an ISO datetime, got {self.at!r}"
                ) from None
        if self.type == "reminder" and not self.message.strip():
            raise ValueError("reminders need a non-empty message")
        if self.type == "watch" and not self.segment.strip():
            raise ValueError("watch alerts need a non-empty segment")
        if (
            isinstance(self.dow, bool)
            or not isinstance(self.dow, int)
            or not -1 <= self.dow <= 6
        ):
            raise ValueError(
                f"dow must be -1 (any day) or 0..6 (Mon..Sun), got {self.dow!r}"
            )
        if not isinstance(self.threshold, (int, float)) or isinstance(
            self.threshold, bool
        ):
            raise ValueError("threshold must be numeric")
        if not 0.0 <= float(self.threshold) <= 100.0:
            raise ValueError("threshold must be within 0-100")
        if not isinstance(self.worth_bar, (int, float)) or isinstance(
            self.worth_bar, bool
        ):
            raise ValueError("worth_bar must be numeric")
        if not 0.0 <= float(self.worth_bar) <= 1.0:
            raise ValueError("worth_bar must be within 0-1")
        if not self.channels:
            raise ValueError("at least one delivery channel is required")
        for ch in self.channels:
            if ch not in CHANNELS:
                raise ValueError(f"unknown channel {ch!r}; expected one of {CHANNELS}")
        _parse_hhmm(self.quiet_start, "quiet_start")
        _parse_hhmm(self.quiet_end, "quiet_end")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["channels"] = list(self.channels)
        return d

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Alert":
        data = dict(raw)
        data["channels"] = tuple(data.get("channels") or ("console", "file"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AlertEvent:
    """One fired alert — what happened, rendered for delivery."""

    alert_id: str
    alert_name: str
    kind: str
    title: str
    lines: List[str]
    dedup_key: str
    held: bool = False  # True when fired inside quiet hours
    fired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def render_card(self) -> str:
        head = f"=== DemandPulse — {self.title} ==="
        body = [head, f"alert: {self.alert_name}  ({self.kind})"]
        if self.held:
            body.append("(held for quiet hours — will deliver after)")
        body.extend(f"• {line}" for line in self.lines)
        body.append("Labels are HYPOTHESIS until verified OBSERVED in corpus.")
        return "\n".join(body)


def _alert_id(name: str, kind: str) -> str:
    seed = f"{kind}:{name}:{datetime.now(timezone.utc).isoformat()}"
    return "al-" + hashlib.sha256(seed.encode()).hexdigest()[:8]


class AlertEngine:
    """Evaluate alert definitions against DemandPulse state.

    ``evaluate`` is pure against the store: it returns the events that are
    due right now (some possibly held for quiet hours) and records their
    dedup keys so they never fire twice. ``run`` evaluates and delivers.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_ALERTS_PATH
        self.alerts: List[Alert] = []
        self.fired_keys: Dict[str, str] = {}  # dedup_key -> fired_at
        self.pending: List[Dict[str, Any]] = []  # held events awaiting quiet-hours end
        self._load()

    # ---- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return  # corrupt store: start empty, never crash the run
        if not isinstance(raw, dict):
            return
        for item in raw.get("alerts") or []:
            if not isinstance(item, dict):
                continue
            try:
                self.alerts.append(Alert.from_dict(item))
            except Exception:
                continue
        fired = raw.get("fired_keys") or {}
        if isinstance(fired, dict):
            self.fired_keys = {str(k): str(v) for k, v in fired.items()}
        pending = raw.get("pending") or []
        if isinstance(pending, list):
            self.pending = [p for p in pending if isinstance(p, dict)]

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "alerts": [a.to_dict() for a in self.alerts],
            "fired_keys": self.fired_keys,
            "pending": self.pending,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---- alert management -------------------------------------------------

    def create(self, kind: str, name: str, **kwargs: Any) -> Alert:
        alert = Alert(id=_alert_id(name, kind), type=kind, name=name, **kwargs)
        self.alerts.append(alert)
        self._persist()
        return alert

    def delete(self, alert_id: str) -> bool:
        before = len(self.alerts)
        self.alerts = [a for a in self.alerts if a.id != alert_id]
        if len(self.alerts) != before:
            self._persist()
            return True
        return False

    def set_enabled(self, alert_id: str, enabled: bool) -> bool:
        for i, a in enumerate(self.alerts):
            if a.id == alert_id:
                data = a.to_dict()
                data["enabled"] = bool(enabled)
                self.alerts[i] = Alert.from_dict(data)
                self._persist()
                return True
        return False

    def get(self, alert_id: str) -> Optional[Alert]:
        for a in self.alerts:
            if a.id == alert_id:
                return a
        return None

    # ---- evaluation ---------------------------------------------------------

    def _mark_fired(self, key: str, now_iso: str) -> bool:
        """Record a dedup key; False when it already fired (skip)."""
        if key in self.fired_keys:
            return False
        self.fired_keys[key] = now_iso
        return True

    def evaluate(self, dp: Any, now: Optional[datetime] = None) -> List[AlertEvent]:
        """Return due events for all enabled alerts. Records dedup keys."""
        now = now or _now_local()
        now_iso = now.astimezone(timezone.utc).isoformat()
        events: List[AlertEvent] = []
        for alert in self.alerts:
            if not alert.enabled:
                continue
            quiet = in_quiet_hours(now, alert.quiet_start, alert.quiet_end)
            if alert.type == "threshold":
                events.extend(self._eval_threshold(alert, dp, now_iso, quiet))
            elif alert.type == "watch":
                events.extend(self._eval_watch(alert, dp, now_iso, quiet))
            elif alert.type == "briefing":
                ev = self._eval_briefing(alert, dp, now, now_iso, quiet)
                if ev:
                    events.append(ev)
            elif alert.type == "reminder":
                ev = self._eval_reminder(alert, now, now_iso, quiet)
                if ev:
                    events.append(ev)
        if events:
            self._persist()
        return events

    def _eval_threshold(
        self, alert: Alert, dp: Any, now_iso: str, quiet: bool
    ) -> List[AlertEvent]:
        events: List[AlertEvent] = []
        for card in getattr(dp, "score_cards", []):
            if not getattr(card, "alert", False):
                continue
            if float(card.composite) < float(alert.threshold):
                continue
            key = f"{alert.id}:card:{card.opportunity_id}"
            if not self._mark_fired(key, now_iso):
                continue
            events.append(
                AlertEvent(
                    alert_id=alert.id,
                    alert_name=alert.name,
                    kind="threshold",
                    title="Opportunity crossed threshold",
                    lines=[
                        f"{card.title} — composite {card.composite:.2f} "
                        f"(tier {card.tier}, bar {float(alert.threshold):.0f})",
                    ],
                    dedup_key=key,
                    held=quiet,
                )
            )
        for opp in getattr(dp, "opportunities", []):
            if float(opp.worth) < float(alert.worth_bar):
                continue
            key = f"{alert.id}:opp:{opp.id}"
            if not self._mark_fired(key, now_iso):
                continue
            events.append(
                AlertEvent(
                    alert_id=alert.id,
                    alert_name=alert.name,
                    kind="threshold",
                    title="High-worth opportunity",
                    lines=[
                        f"{opp.title} — worth {opp.worth:.2f} "
                        f"(bar {float(alert.worth_bar):.2f})",
                    ],
                    dedup_key=key,
                    held=quiet,
                )
            )
        return events

    def _eval_watch(
        self, alert: Alert, dp: Any, now_iso: str, quiet: bool
    ) -> List[AlertEvent]:
        events: List[AlertEvent] = []
        for sig in getattr(dp, "signals", []):
            if sig.segment != alert.segment:
                continue
            key = f"{alert.id}:sig:{sig.id}"
            if not self._mark_fired(key, now_iso):
                continue
            events.append(
                AlertEvent(
                    alert_id=alert.id,
                    alert_name=alert.name,
                    kind="watch",
                    title=f"New demand signal in '{alert.segment}'",
                    lines=[
                        f"{sig.need[:120]} [{sig.kind}, "
                        f"confidence {sig.confidence:.2f}]",
                    ],
                    dedup_key=key,
                    held=quiet,
                )
            )
        return events

    def _period_key(self, alert: Alert, now: datetime) -> Optional[str]:
        """Dedup period for scheduled alerts; None when not yet due today."""
        hh, mm = _parse_hhmm(alert.time, "time")
        if alert.recurrence == "monthly":
            due_this_month = now.replace(
                day=1, hour=hh, minute=mm, second=0, microsecond=0
            )
            if now < due_this_month:
                return None
            return now.strftime("%Y-%m")
        due_today = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now < due_today:
            return None
        if alert.recurrence == "daily":
            return now.strftime("%Y-%m-%d")
        if alert.recurrence == "weekly":
            if alert.dow != -1 and now.weekday() != alert.dow:
                return None
            return now.strftime("%Y-W%V")
        return now.strftime("%Y-%m-%dT%H:%M")

    def _eval_briefing(
        self, alert: Alert, dp: Any, now: datetime, now_iso: str, quiet: bool
    ) -> Optional[AlertEvent]:
        period = self._period_key(alert, now)
        if period is None:
            return None
        key = f"{alert.id}:brief:{period}"
        if not self._mark_fired(key, now_iso):
            return None
        signals = getattr(dp, "signals", [])
        opps = sorted(getattr(dp, "opportunities", []), key=lambda o: -float(o.worth))
        hot_cards = [
            c for c in getattr(dp, "score_cards", []) if getattr(c, "alert", False)
        ]
        lines = [f"{len(signals)} signals tracked, {len(opps)} opportunities scored"]
        for opp in opps[:3]:
            lines.append(f"top: {opp.title} (worth {opp.worth:.2f})")
        for card in hot_cards[:3]:
            lines.append(f"above bar: {card.title} ({card.composite:.2f}, {card.tier})")
        if not opps and not hot_cards:
            lines.append("nothing above the bar yet — seed with: levi demand --scan …")
        return AlertEvent(
            alert_id=alert.id,
            alert_name=alert.name,
            kind="briefing",
            title=f"Demand briefing — {now.strftime('%A')}",
            lines=lines,
            dedup_key=key,
            held=quiet,
        )

    def _eval_reminder(
        self, alert: Alert, now: datetime, now_iso: str, quiet: bool
    ) -> Optional[AlertEvent]:
        if alert.recurrence == "once":
            at = datetime.fromisoformat(alert.at)
            if at.tzinfo is None:
                at = at.replace(tzinfo=now.tzinfo)
            if now < at:
                return None
            key = f"{alert.id}:at:{alert.at}"
        else:
            period = self._period_key(alert, now)
            if period is None:
                return None
            key = f"{alert.id}:rem:{period}"
        if not self._mark_fired(key, now_iso):
            return None
        return AlertEvent(
            alert_id=alert.id,
            alert_name=alert.name,
            kind="reminder",
            title="Reminder",
            lines=[alert.message],
            dedup_key=key,
            held=quiet,
        )

    # ---- delivery -----------------------------------------------------------

    def deliver(
        self,
        event: AlertEvent,
        channels: Optional[Tuple[str, ...]] = None,
        outbox: Optional[Path] = None,
        notifier: Any = None,
    ) -> Dict[str, str]:
        """Deliver one event; returns per-channel status.

        "sms" sends for real via the Pulse device alerter path
        (termux-sms-send); "email" sends for real via stdlib SMTP when the
        LEVI_SMTP_* credentials are set — both report "not_configured"
        when their credentials are missing, never faked. "whatsapp" is
        gated until the WhatsApp side-chat relay task exists (or a
        WhatsApp API endpoint is configured). "webhook" POSTs the alert
        JSON to LEVI_ALERT_WEBHOOK_URL; "sheets" POSTs it to
        LEVI_SHEETS_WEBHOOK_URL — both report "not_configured" naming
        their var when unset, never faked. "push" routes through the
        NeighborOS notifier when one is attached and reports its honest
        summary status — never silently dropped, never falsely claimed;
        without a notifier it stays "not_configured".
        """
        from levi.demand import failover as fomod

        alert = self.get(event.alert_id)
        chans = channels or (alert.channels if alert else ("console", "file"))
        outbox = outbox or DEFAULT_OUTBOX_PATH
        status: Dict[str, str] = {}
        for ch in chans:
            if ch == "console":
                print(event.render_card())
                print()
                status[ch] = "delivered"
            elif ch == "file":
                outbox.parent.mkdir(parents=True, exist_ok=True)
                with outbox.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event.to_dict()) + "\n")
                status[ch] = "delivered"
            elif ch == "push":
                if notifier is None:
                    status[ch] = "not_configured"
                else:
                    push_backends = [
                        b for b in notifier.backends if b in PUSH_BACKENDS
                    ]
                    if not push_backends:
                        status[ch] = "not_configured"
                    else:
                        per = notifier.send(
                            {
                                "id": f"demandpulse:{event.dedup_key}",
                                "title": f"DemandPulse — {event.title}",
                                "body": event.render_card(),
                                "kind": f"demandpulse:{event.kind}",
                                "cell": None,
                            },
                            backends=push_backends,
                        )
                        status[ch] = _summarize_send(per)
            elif ch == "sms":
                st, detail = fomod.send_sms(event.title, event.render_card())
                status[ch] = (
                    "delivered"
                    if st == "delivered"
                    else "not_configured"
                    if st == "unconfigured"
                    else f"failed: {detail}"
                )
            elif ch == "email":
                st, detail = fomod.send_email(event.title, event.render_card())
                status[ch] = (
                    "delivered"
                    if st == "delivered"
                    else "not_configured"
                    if st == "unconfigured"
                    else f"failed: {detail}"
                )
            elif ch == "whatsapp":
                st, detail = fomod.send_whatsapp(event.title, event.render_card())
                status[ch] = {
                    "delivered": "delivered",
                    "queued": "queued_for_whatsapp_relay",
                    "needs_setup": "needs_whatsapp_chat_setup",
                }.get(st, f"failed: {detail}")
            elif ch in ("webhook", "sheets"):
                sender = fomod.send_webhook if ch == "webhook" else fomod.send_sheets
                st, detail = sender(event.title, event.render_card())
                status[ch] = (
                    "delivered"
                    if st == "delivered"
                    else "not_configured"
                    if st == "unconfigured"
                    else f"failed: {detail}"
                )
            else:
                status[ch] = "unknown_channel"
        return status

    def deliver_failover(
        self,
        event: AlertEvent,
        order: Optional[Tuple[str, ...]] = None,
        chain_log: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run the failover chain for one event: sms -> email -> whatsapp
        -> webhook -> sheets.

        One pipeline fails -> the alert goes to the next. The first
        confirmed delivery wins. Every dispatch is chain-logged (L3) and
        "delivered" is only reported on downstream confirmation (L2).
        Severity sent to the webhook/sheets JSON legs: threshold -> high,
        watch -> medium, briefing/reminder -> info.
        Returns the chain report as a dict.
        """
        from levi.demand import failover as fomod

        severity = {"threshold": "high", "watch": "medium"}.get(event.kind, "info")
        report = fomod.dispatch(
            alert_id=event.alert_id,
            dedup_key=event.dedup_key,
            title=event.title,
            body=event.render_card(),
            order=order or fomod.DEFAULT_ORDER,
            severity=severity,
            chain_log=chain_log,
        )
        return report.to_dict()

    def run(
        self,
        dp: Any,
        now: Optional[datetime] = None,
        outbox: Optional[Path] = None,
        notifier: Any = None,
    ) -> Dict[str, Any]:
        """Evaluate and deliver. Held events wait out quiet hours.

        Returns a receipt: {fired, delivered, held, flushed, channel_status,
        failover}. Alerts whose channels include any of sms/email/whatsapp
        are delivered through the failover chain (first confirmed delivery
        wins) instead of per-channel.
        """
        now = now or _now_local()
        events = self.evaluate(dp, now)
        receipt: Dict[str, Any] = {
            "fired": len(events),
            "delivered": 0,
            "held": 0,
            "flushed": 0,
            "channel_status": {},
            "failover": [],
        }
        for event in events:
            if event.held:
                self.pending.append(event.to_dict())
                receipt["held"] += 1
            else:
                alert = self.get(event.alert_id)
                chans = alert.channels if alert else ("console", "file")
                fo_chans = [c for c in chans if c in FAILOVER_CHANNELS]
                if fo_chans:
                    from levi.demand import failover as fomod

                    chain = self.deliver_failover(
                        event,
                        order=tuple(c for c in fomod.DEFAULT_ORDER if c in fo_chans)
                        or fomod.DEFAULT_ORDER,
                    )
                    receipt["failover"].append(chain)
                    rest = tuple(c for c in chans if c not in FAILOVER_CHANNELS)
                    status = self.deliver(
                        event, channels=rest, outbox=outbox, notifier=notifier
                    ) if rest else {}
                    status["failover"] = (
                        f"delivered via {chain['delivered_via']}"
                        if chain["final"] == "delivered"
                        else "held: "
                        + "; ".join(
                            f"{a['channel']}={a['status']}" for a in chain["attempts"]
                        )
                    )
                else:
                    status = self.deliver(event, outbox=outbox, notifier=notifier)
                receipt["delivered"] += 1
                for ch, st in status.items():
                    receipt["channel_status"].setdefault(ch, []).append(st)
        # flush previously held events once quiet hours end
        still_pending: List[Dict[str, Any]] = []
        for raw in self.pending:
            alert = self.get(raw.get("alert_id", ""))
            if alert and not in_quiet_hours(now, alert.quiet_start, alert.quiet_end):
                event = AlertEvent(
                    **{
                        k: v
                        for k, v in raw.items()
                        if k in AlertEvent.__dataclass_fields__
                    }
                )
                event.held = False
                status = self.deliver(event, outbox=outbox, notifier=notifier)
                receipt["flushed"] += 1
                for ch, st in status.items():
                    receipt["channel_status"].setdefault(ch, []).append(st)
            else:
                still_pending.append(raw)
        if len(still_pending) != len(self.pending):
            self.pending = still_pending
            self._persist()
        return receipt
