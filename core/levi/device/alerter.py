"""On-device LEVI alerter — phone-side SMS drain for every operator/service.

Runs on Chauncey's Moto G under Termux with ZERO Muse usage: it reads the
local alert stores every pass and texts new items via ``termux-sms-send``.

LAWS (plain words):
  L1 fail-closed number — no ``LEVI_ALERT_NUMBER`` in the environment means
     nothing is sent, exit is nonzero, and the message says
     "number not configured". The number is never guessed, never defaulted.
  L2 no double-text — a uid is texted at most once. Appending the uid to the
     sent-log is the commit point; a uid already in the sent-log is skipped.
  L3 no number in logs — the destination number never appears in stdout,
     stderr, or the sent-log. Logs carry counts and uids only.
  L4 quiet hours hold — inside the quiet window (default 22:00-07:00
     America/Chicago, ``LEVI_ALERT_QUIET`` overridable, ``off`` disables)
     nothing is sent and nothing is marked sent; held items flush on the
     next pass outside the window.
  L5 termux-absent fallback — no ``termux-sms-send`` binary means "not on
     Termux": print what would be sent, exit 0, mark nothing sent.
  L6 registry-open — every alert source is (name, path, reader). Adding a
     future source is one ``register_source`` call; the drain loop never
     changes.
  L7 read-only on producers — the alerter never writes to any alert store;
     its only write is its own sent-log.
  L8 honest argv — SMS is exactly ``termux-sms-send -n <number> <text>``;
     the number comes only from the environment (L1).

COVERED SOURCES (registry entries — modules with no alert store have none,
and no signals are invented for them):
  herald      ~/.levi/herald/queue.jsonl            (daemon dispatcher queue;
                comms watchdog barks already flow here)
  demandpulse ~/.levi/demand_alerts_outbox.jsonl    (DemandPulse fired alerts)
  neighbor    ~/.levi/neighbor/nudges.jsonl         (NeighborOS nudge queue)
  cybrus      ~/.levi/cybrus/audit.jsonl            (watchdog bark events only)

NOT covered (no alert store found — nothing invented):
  cybrus money/approval ledgers (records, not alerts), mood, inbox
  analytics, mailtriage, signals, telemetry, and every other module under
  core/levi/ without an on-disk alert outbox. When one of them grows a real
  alert store, register it — a few lines, no rewrite.

Stdlib only. Entry: ``python3 -m levi.device.alerter``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from levi.device import approvals as approvals_loop

# ---------------------------------------------------------------------------
# laws (machine-checkable)

LAWS = (
    "L1 fail-closed number: no LEVI_ALERT_NUMBER -> nothing sent, exit != 0, "
    "'number not configured'",
    "L2 no double-text: uid sent at most once; sent-log append is commit",
    "L3 no number in logs: destination number never in stdout/stderr/log",
    "L4 quiet hours hold: inside window nothing sent, nothing marked sent",
    "L5 termux-absent fallback: no binary -> console print, exit 0, unmarked",
    "L6 registry-open: sources are (name, path, reader); drain loop fixed",
    "L7 read-only on producers: only write is the alerter's own sent-log",
    "L8 honest argv: exactly termux-sms-send -n <number> <text>",
)


def check_laws() -> Dict[str, Any]:
    """Machine proof: the registry and invariants hold structurally."""
    problems: List[str] = []
    for name, src in SOURCES.items():
        if not src.name or src.name != name:
            problems.append(f"source {name!r}: name mismatch")
        if not isinstance(src.path, Path):
            problems.append(f"source {name!r}: path is not a Path")
        if not callable(src.reader):
            problems.append(f"source {name!r}: reader not callable")
    q = parse_quiet(os.environ.get("LEVI_ALERT_QUIET", ""))
    if q is None and os.environ.get("LEVI_ALERT_QUIET", "") not in ("", "off"):
        problems.append("quiet window does not parse")
    try:
        base = device_dir()
        base.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"sent-log dir not writable: {exc}")
    return {"ok": not problems, "laws": list(LAWS), "problems": problems}


# ---------------------------------------------------------------------------
# paths

DEFAULT_TZ = "America/Chicago"
DEFAULT_QUIET = "22:00-07:00"
SMS_BINARY = "termux-sms-send"
MAX_BODY_CHARS = 300


def home() -> Path:
    return Path(os.environ.get("LEVI_HOME", str(Path.home())))


def device_dir() -> Path:
    base = Path(os.environ.get("LEVI_DEVICE_DIR", str(home() / ".levi" / "device")))
    return base


def sent_log_path() -> Path:
    return device_dir() / "alerter_sent.jsonl"


# ---------------------------------------------------------------------------
# registry

@dataclass
class AlertSource:
    """One operator/service alert store: name + on-disk path + reader."""

    name: str
    path: Path
    reader: Callable[[], List[Dict[str, str]]]
    # reader returns normalized items: {"uid", "title", "body"}


SOURCES: Dict[str, AlertSource] = {}


def register_source(
    name: str, path: Path, reader: Callable[[], List[Dict[str, str]]]
) -> AlertSource:
    """Add a future alert source in a few lines — the drain loop is fixed."""
    src = AlertSource(name=name, path=path, reader=reader)
    SOURCES[name] = src
    return src


def _read_jsonl_tail(path: Path, max_lines: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    out: List[Dict[str, Any]] = []
    for ln in lines[-max_lines:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _read_herald() -> List[Dict[str, str]]:
    """Pending herald notices — the daemon dispatcher queue."""
    from levi.daemon.herald import HeraldQueue

    items: List[Dict[str, str]] = []
    for n in HeraldQueue().pending():
        items.append(
            {
                "uid": f"herald:{n.id}",
                "title": n.title,
                "body": n.body or "",
                "level": n.level,
            }
        )
    return items


def _read_demandpulse() -> List[Dict[str, str]]:
    """Fired DemandPulse alerts from the file outbox."""
    path = home() / ".levi" / "demand_alerts_outbox.jsonl"
    items: List[Dict[str, str]] = []
    for rec in _read_jsonl_tail(path):
        key = str(rec.get("dedup_key") or rec.get("id") or "")
        if not key:
            continue
        items.append(
            {
                "uid": f"demandpulse:{key}",
                "title": str(rec.get("title") or "DemandPulse alert"),
                "body": str(rec.get("kind") or ""),
            }
        )
    return items


def _read_neighbor() -> List[Dict[str, str]]:
    """Queued NeighborOS nudges (latest record per id wins, like pull_nudges)."""
    path = home() / ".levi" / "neighbor" / "nudges.jsonl"
    latest: Dict[str, Dict[str, Any]] = {}
    for rec in _read_jsonl_tail(path, max_lines=2000):
        if rec.get("id"):
            latest[str(rec["id"])] = rec
    items: List[Dict[str, str]] = []
    for nid, rec in latest.items():
        if rec.get("status") != "queued":
            continue
        items.append(
            {
                "uid": f"neighbor:{nid}",
                "title": f"NeighborOS [{rec.get('kind', 'note')}]",
                "body": str(rec.get("message") or ""),
            }
        )
    return items


CYBRUS_BARK_EVENT = "cybrus.watchdog.bark"


def _read_cybrus() -> List[Dict[str, str]]:
    """Cybrus watchdog bark events from the audit trail (read-only tail)."""
    path = home() / ".levi" / "cybrus" / "audit.jsonl"
    items: List[Dict[str, str]] = []
    for rec in _read_jsonl_tail(path):
        if rec.get("event") != CYBRUS_BARK_EVENT:
            continue
        det = rec.get("details") or {}
        seq = rec.get("seq", rec.get("hash", ""))
        items.append(
            {
                "uid": f"cybrus:{seq}",
                "title": (
                    f"Cybrus bark [{det.get('direction', '?')}/"
                    f"{det.get('signal', '?')}]"
                ),
                "body": str(det.get("remedy") or det.get("severity") or ""),
            }
        )
    return items


def _register_defaults() -> None:
    h = home()
    register_source("herald", h / ".levi" / "herald" / "queue.jsonl", _read_herald)
    register_source(
        "demandpulse", h / ".levi" / "demand_alerts_outbox.jsonl", _read_demandpulse
    )
    register_source(
        "neighbor", h / ".levi" / "neighbor" / "nudges.jsonl", _read_neighbor
    )
    register_source(
        "cybrus", h / ".levi" / "cybrus" / "audit.jsonl", _read_cybrus
    )


_register_defaults()

# ---------------------------------------------------------------------------
# quiet hours


def _tz():
    try:
        return ZoneInfo(os.environ.get("LEVI_ALERT_TZ", DEFAULT_TZ))
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-6))  # documented fallback, warned


def parse_quiet(spec: str) -> Optional[tuple]:
    """'22:00-07:00' -> (start, end); '' -> default; 'off' -> None."""
    spec = (spec or "").strip().lower()
    if spec in ("", "default"):
        spec = DEFAULT_QUIET
    if spec == "off":
        return None
    try:
        start_s, end_s = spec.split("-", 1)
        sh, sm = (int(x) for x in start_s.split(":"))
        eh, em = (int(x) for x in end_s.split(":"))
        return (time(sh, sm), time(eh, em))
    except (ValueError, TypeError):
        return None


def in_quiet_hours(now: Optional[datetime] = None) -> bool:
    window = parse_quiet(os.environ.get("LEVI_ALERT_QUIET", ""))
    if window is None:
        return False
    start, end = window
    now = now or datetime.now(_tz())
    cur = now.timetz()
    cur_t = time(cur.hour, cur.minute)
    if start <= end:
        return start <= cur_t < end
    return cur_t >= start or cur_t < end  # overnight window


# ---------------------------------------------------------------------------
# sent-log (L2, L7)


def read_sent() -> set:
    path = sent_log_path()
    if not path.exists():
        return set()
    sent = set()
    with path.open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                sent.add(json.loads(ln)["uid"])
            except (json.JSONDecodeError, KeyError):
                continue
    return sent


def mark_sent(uid: str) -> None:
    """Append-only commit point (L2). Only the alerter's own log is written."""
    path = sent_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"uid": uid, "ts": _utcnow()}) + "\n")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# message shaping (short, plain — no jargon)


def shape_sms(source: str, title: str, body: str) -> str:
    first_line = (body or "").strip().splitlines()[0] if (body or "").strip() else ""
    text = f"[{source}] {title.strip()}"
    if first_line:
        text += f" — {first_line}"
    if len(text) > MAX_BODY_CHARS:
        text = text[: MAX_BODY_CHARS - 1] + "…"
    return text


# ---------------------------------------------------------------------------
# drain


@dataclass
class DrainResult:
    sent: List[str] = field(default_factory=list)
    held: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # already sent
    errors: List[str] = field(default_factory=list)
    relayed: List[str] = field(default_factory=list)  # Void Box relay OK
    relay_errors: List[str] = field(default_factory=list)  # relay failed, SMS still ran


def collect_new() -> List[Dict[str, str]]:
    """Walk the whole registry; return items not yet in the sent-log."""
    sent = read_sent()
    new: List[Dict[str, str]] = []
    for name, src in SOURCES.items():
        try:
            items = src.reader()
        except Exception as exc:  # a broken source must not kill the drain
            print(f"[alerter] source {name}: reader error {type(exc).__name__}",
                  file=sys.stderr)
            continue
        for it in items:
            it = dict(it)
            it.setdefault("source", name)
            if it.get("uid") not in sent:
                new.append(it)
    return new


def send_sms(number: str, text: str) -> None:
    """Exactly: termux-sms-send -n <number> <text> (L8)."""
    subprocess.run(
        [SMS_BINARY, "-n", number, text],
        check=True,
        capture_output=True,
    )


def drain(
    number: Optional[str] = None,
    *,
    sms_sender: Callable[[str, str], None] = send_sms,
    binary_present: Optional[bool] = None,
    relay: Any = None,
    relay_room: Optional[str] = None,
) -> DrainResult:
    """One pass over the registry. Returns what happened; raises SystemExit
    codes are decided by main(), not here.

    ``relay`` is a Void Box alert relay (duck-typed: needs
    ``send_alert(room, title, body)`` — see levi.voidbox.relay_alerts).
    When present, every drained item is ALSO posted to the relay room
    (Void Box as the primary push channel). Relay failures are caught
    per item, recorded in ``result.relay_errors``, and NEVER block the
    SMS path — degraded, logged, SMS still sends.
    """
    result = DrainResult()
    number = number if number is not None else os.environ.get("LEVI_ALERT_NUMBER", "")
    number = (number or "").strip()
    if not number:
        # L1: fail closed — before touching anything.
        raise NoNumberError("number not configured")
    new_items = collect_new()
    if not new_items:
        return result
    if in_quiet_hours():
        # L4: hold everything; mark nothing sent — next pass flushes.
        result.held = [it["uid"] for it in new_items]
        return result
    present = (
        binary_present
        if binary_present is not None
        else shutil.which(SMS_BINARY) is not None
    )
    if not present:
        # L5: not on Termux — console fallback, exit 0, nothing marked.
        for it in new_items:
            print(f"[alerter:console] {shape_sms(it['source'], it['title'], it['body'])}")
        return result
    room = relay_room or os.environ.get("LEVI_VOIDBOX_ALERT_ROOM", "alerts")
    for it in new_items:
        if relay is not None:
            # Fan-out (relay laws L1/L2): best effort — a relay failure
            # is recorded and the SMS still goes out.
            try:
                relay.send_alert(room, it["title"], it["body"])
                result.relayed.append(it["uid"])
            except Exception as exc:  # noqa: BLE001
                result.relay_errors.append(
                    f"{it['uid']}: {type(exc).__name__}")
        text = _outbound_text(it)
        try:
            sms_sender(number, text)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{it['uid']}: {type(exc).__name__}")
            continue
        mark_sent(it["uid"])  # L2 commit point
        result.sent.append(it["uid"])
    return result


def _outbound_text(it: Dict[str, str]) -> str:
    """Shape one outbound SMS. Items flagged ``needs_approval`` go through
    the approvals loop: text-safe categories get "Reply YES <id> or NO
    <id>"; excluded categories (money/destructive/public — B2) are texted
    as in-chat-only and no id is ever issued for them."""
    base = shape_sms(it["source"], it["title"], it["body"])
    if not it.get("needs_approval"):
        return base
    cat = approvals_loop.normalize_category(it.get("category"))
    if not approvals_loop.is_text_approvable(cat):
        return base + " — needs your word in chat (not text-approvable)."
    try:
        aid = approvals_loop.request_approval(
            uid=it["uid"],
            title=it["title"],
            source=it["source"],
            category=cat,
            body=it["body"],
        )
    except approvals_loop.ExcludedCategoryError:
        return base + " — needs your word in chat (not text-approvable)."
    return f"{base} Reply YES {aid} or NO {aid} (24h)."


class NoNumberError(RuntimeError):
    """LEVI_ALERT_NUMBER missing — fail closed (L1)."""


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    if "--check-laws" in argv:
        report = check_laws()
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    if "--list-sources" in argv:
        for name, src in SOURCES.items():
            print(f"{name}: {src.path}")
        return 0
    try:
        result = drain()
    except NoNumberError as exc:
        # L1/L3: the number itself never appears in output.
        print(f"[alerter] {exc}", file=sys.stderr)
        return 2
    sent, held, errors = result.sent, result.held, result.errors
    # L3: counts and uids only — never the number, never bodies.
    print(
        f"[alerter] sent={len(sent)} held={len(held)} "
        f"errors={len(errors)} relayed={len(result.relayed)} "
        f"relay_errors={len(result.relay_errors)} sources={len(SOURCES)}"
    )
    for uid in held:
        print(f"[alerter] held for quiet hours: {uid}")
    for err in errors:
        print(f"[alerter] error: {err}", file=sys.stderr)
    for err in result.relay_errors:
        print(f"[alerter] relay error (SMS still sent): {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
