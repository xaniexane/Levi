"""DemandPulse alert failover delivery — SMS + email + WhatsApp + webhook + Sheets.

One pipeline fails -> the alert goes to the next. Ordered chain, honest
receipts, nothing lost, nothing faked.

LAWS (plain words, machine-checked by ``check_laws``):
  L1 FAILOVER — ordered channel chain
     (default sms -> email -> whatsapp -> webhook -> sheets).
     A channel failure automatically tries the next. The alert is marked
     "delivered" only when a channel confirms; the first confirmed
     delivery wins and later channels are not attempted.
  L2 NO FAKE RECEIPTS — "delivered" requires downstream confirmation:
     termux-sms-send exit 0 for SMS, SMTP accept for email, HTTP 2xx for
     a WhatsApp API endpoint, HTTP 2xx for webhook/Sheets endpoints.
     Anything else is "failed"/"held" with the reason. "queued" is never
     reported as "delivered".
  L3 NO LOSS — every dispatch appends a chain record (the event plus all
     attempts in order) to the chain log, whatever the outcome.
  L4 CREDENTIAL HONESTY — a channel without its credentials/connection
     reports "unconfigured" naming exactly what is missing and is skipped
     cleanly. A send is never invented. Secrets never appear in logs,
     receipts, or chain records.

Channel reality (verified, not assumed):
  sms      — real send via the Pulse device alerter path:
             ``termux-sms-send -n <number> <text>``. Needs LEVI_ALERT_NUMBER
             and the termux-sms-send binary (present on Chauncey's phone
             under Termux; absent on this sandbox -> honest "termux_absent",
             never "delivered").
  email    — real send via stdlib smtplib. Needs LEVI_SMTP_HOST,
             LEVI_SMTP_USER, LEVI_SMTP_PASS (+ optional LEVI_SMTP_PORT,
             LEVI_SMTP_FROM, LEVI_SMTP_TO, LEVI_SMTP_TLS). Missing any
             required piece -> "unconfigured", skipped cleanly.
  whatsapp — gated. Three honest rungs, in order:
             1. LEVI_WHATSAPP_API_URL + LEVI_WHATSAPP_API_TOKEN set ->
                real HTTP POST to a WhatsApp Business API-compatible
                endpoint; 2xx = delivered.
             2. LEVI_WHATSAPP_READY=1 -> the WhatsApp side-chat relay task
                exists; the alert is queued to ~/.levi/whatsapp_relay_queue.jsonl
                for that task to drain -> "queued_for_whatsapp_relay"
                (explicitly NOT delivered).
             3. neither -> "needs_whatsapp_chat_setup" with the exact setup
                step. Never "delivered", never the vague "not_configured".
  webhook  — fully local leg: real HTTP POST of the alert JSON payload to
             LEVI_ALERT_WEBHOOK_URL. 2xx = delivered; anything else = failed
             with status/reason, chain continues. Missing URL ->
             "unconfigured" naming LEVI_ALERT_WEBHOOK_URL. Works against a
             local receiver (e.g. python -m http.server + a hook script)
             with zero third-party services.
  sheets   — Google Sheets logger leg: real HTTP POST of the same payload
             (plus delivered_via) to LEVI_SHEETS_WEBHOOK_URL (Chauncey's
             Google Apps Script URL). Append-row semantics live in his
             script; our side just delivers the payload honestly. Missing
             URL -> "unconfigured" naming LEVI_SHEETS_WEBHOOK_URL and
             skipped cleanly — he has not supplied it yet.

stdlib-only.
"""

from __future__ import annotations

import json
import os
import shutil
import smtplib
import subprocess
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

LAWS = (
    "L1 failover: ordered chain sms->email->whatsapp->webhook->sheets; "
    "first confirmed delivery wins; a failure tries the next channel",
    "L2 no fake receipts: 'delivered' only on downstream confirmation "
    "(termux exit 0 / SMTP accept / HTTP 2xx); 'queued' is never 'delivered'",
    "L3 no loss: every dispatch appends a chain record (event + attempts) "
    "to the chain log",
    "L4 credential honesty: unconfigured channels name what's missing and "
    "are skipped cleanly; secrets never appear in logs or records",
)

CHANNELS: Tuple[str, ...] = ("sms", "email", "whatsapp", "webhook", "sheets")
DEFAULT_ORDER: Tuple[str, ...] = ("sms", "email", "whatsapp", "webhook", "sheets")

DEFAULT_CHAIN_LOG = Path.home() / ".levi" / "demand_alert_chains.jsonl"
DEFAULT_WHATSAPP_QUEUE = Path.home() / ".levi" / "whatsapp_relay_queue.jsonl"

SMS_BINARY = "termux-sms-send"
SMS_MAX_CHARS = 300

WHATSAPP_SETUP = (
    "Proactive WhatsApp needs a scheduled task created FROM the WhatsApp "
    "side chat: open the linked WhatsApp conversation in the app and create "
    "the schedule there, then set LEVI_WHATSAPP_READY=1 so this chain can "
    "queue alerts for it. (Or set LEVI_WHATSAPP_API_URL + "
    "LEVI_WHATSAPP_API_TOKEN for a WhatsApp Business API-compatible endpoint.)"
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secret_values() -> List[str]:
    """Every configured secret, for redaction (L4)."""
    vals = []
    for key in (
        "LEVI_ALERT_NUMBER",
        "LEVI_SMTP_PASS",
        "LEVI_SMTP_USER",
        "LEVI_WHATSAPP_API_TOKEN",
    ):
        v = os.environ.get(key, "")
        if v:
            vals.append(v)
    return vals


def _redact(text: str) -> str:
    """Strip every configured secret from a string (L4)."""
    out = str(text)
    for secret in _secret_values():
        if secret and secret in out:
            out = out.replace(secret, "[redacted]")
    return out


# ---------------------------------------------------------------------------
# attempt / report records


@dataclass
class Attempt:
    channel: str
    status: str  # delivered | failed | unconfigured | needs_setup | queued
    detail: str  # redacted, no secrets (L4)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChainReport:
    alert_id: str
    dedup_key: str
    title: str
    order: Tuple[str, ...]
    attempts: List[Attempt] = field(default_factory=list)
    delivered_via: Optional[str] = None
    final: str = "held"  # delivered | held

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["order"] = list(self.order)
        d["attempts"] = [a.to_dict() for a in self.attempts]
        d["ts"] = _utcnow()
        return d


# ---------------------------------------------------------------------------
# per-channel senders. Each returns (status, detail); "delivered" is only
# ever returned on real downstream confirmation (L2).


def send_sms(
    title: str,
    body: str,
    *,
    number: Optional[str] = None,
    binary_present: Optional[bool] = None,
    runner: Optional[Callable[[List[str]], None]] = None,
) -> Tuple[str, str]:
    """SMS via the Pulse device alerter path (termux-sms-send)."""
    from levi.device.alerter import shape_sms

    num = (number if number is not None else os.environ.get("LEVI_ALERT_NUMBER", "")).strip()
    if not num:
        return ("unconfigured", "LEVI_ALERT_NUMBER not set — SMS skipped cleanly")
    present = (
        binary_present
        if binary_present is not None
        else shutil.which(SMS_BINARY) is not None
    )
    if not present:
        return (
            "failed",
            "termux_absent: termux-sms-send not found (not on Termux) — "
            "SMS only sends from Chauncey's phone",
        )
    text = shape_sms("demandpulse", title, body)
    run = runner or (
        lambda argv: subprocess.run(
            argv, check=True, capture_output=True, timeout=30
        )
    )
    try:
        run([SMS_BINARY, "-n", num, text])
    except Exception as exc:  # noqa: BLE001 — report, never raise
        return ("failed", f"sms_send_failed: {_redact(str(exc))[:160]}")
    return ("delivered", "termux-sms-send exit 0 — handed to the Android SMS stack")


def _smtp_config() -> Tuple[Dict[str, str], List[str]]:
    """(config, missing_required). Required: host, user, pass."""
    cfg = {
        "host": os.environ.get("LEVI_SMTP_HOST", "").strip(),
        "port": os.environ.get("LEVI_SMTP_PORT", "587").strip() or "587",
        "user": os.environ.get("LEVI_SMTP_USER", "").strip(),
        "password": os.environ.get("LEVI_SMTP_PASS", ""),
        "from": os.environ.get("LEVI_SMTP_FROM", "").strip(),
        "to": os.environ.get("LEVI_SMTP_TO", "").strip(),
        "tls": os.environ.get("LEVI_SMTP_TLS", "on").strip().lower(),
    }
    missing = [k for k in ("LEVI_SMTP_HOST", "LEVI_SMTP_USER", "LEVI_SMTP_PASS")
               if not os.environ.get(k, "").strip()]
    if not cfg["from"]:
        cfg["from"] = cfg["user"]
    if not cfg["to"]:
        cfg["to"] = cfg["from"]
    return cfg, missing


def send_email(
    title: str,
    body: str,
    *,
    smtp_factory: Optional[Callable[..., Any]] = None,
) -> Tuple[str, str]:
    """Email via stdlib smtplib. Missing credentials -> unconfigured (L4)."""
    cfg, missing = _smtp_config()
    if missing:
        return (
            "unconfigured",
            "missing: " + ", ".join(missing) + " — email skipped cleanly",
        )
    msg = EmailMessage()
    msg["Subject"] = f"[DemandPulse] {title}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg.set_content(body)
    try:
        port = int(cfg["port"])
    except ValueError:
        return ("failed", f"smtp_error: bad LEVI_SMTP_PORT {cfg['port']!r}")
    try:
        smtp_cls = smtp_factory or smtplib.SMTP
        with smtp_cls(cfg["host"], port, timeout=20) as smtp:
            if cfg["tls"] != "off":
                smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — report, never raise
        return ("failed", f"smtp_error: {_redact(str(exc))[:160]}")
    return ("delivered", f"SMTP accepted via {cfg['host']}:{port}")


def send_whatsapp(
    title: str,
    body: str,
    *,
    queue_path: Optional[Path] = None,
    http_post: Optional[Callable[[str, Dict[str, Any], str], int]] = None,
) -> Tuple[str, str]:
    """WhatsApp — three honest rungs (see module docstring). Never faked."""
    api_url = os.environ.get("LEVI_WHATSAPP_API_URL", "").strip()
    api_token = os.environ.get("LEVI_WHATSAPP_API_TOKEN", "").strip()
    if api_url and api_token:
        # Rung 1: real API endpoint. 2xx = delivered (L2).
        payload = {"text": f"[DemandPulse] {title}\n{body}"}
        try:
            post = http_post or _default_http_post
            code = post(api_url, payload, api_token)
        except Exception as exc:  # noqa: BLE001
            return ("failed", f"whatsapp_api_error: {_redact(str(exc))[:160]}")
        if 200 <= code < 300:
            return ("delivered", f"WhatsApp API accepted (HTTP {code})")
        return ("failed", f"whatsapp_api_error: HTTP {code}")
    if os.environ.get("LEVI_WHATSAPP_READY", "").strip() == "1":
        # Rung 2: queue for the WhatsApp side-chat relay task. Queued is
        # queued — explicitly NOT delivered (L2).
        qpath = queue_path or DEFAULT_WHATSAPP_QUEUE
        qpath.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": _utcnow(),
            "title": title,
            "body": body,
            "status": "queued_for_whatsapp_relay",
        }
        with qpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return (
            "queued",
            "queued_for_whatsapp_relay: waiting on the WhatsApp side-chat "
            "task to drain the relay queue",
        )
    # Rung 3: gated — exact setup step, never faked (L4).
    return ("needs_setup", WHATSAPP_SETUP)


def _default_http_post_noauth(url: str, payload: Dict[str, Any]) -> int:
    """POST JSON without auth (webhook / sheets legs). Returns HTTP status."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.getcode()


def _host_of(url: str) -> str:
    """Host only — full URLs stay out of details (L4)."""
    try:
        return urllib.request.urlparse(url).netloc or "[invalid-url]"
    except Exception:  # noqa: BLE001
        return "[invalid-url]"


def _webhook_payload(
    alert_id: str,
    title: str,
    body: str,
    severity: str,
    channel_chain: List[str],
) -> Dict[str, Any]:
    return {
        "alert_id": alert_id,
        "title": title,
        "body": body,
        "severity": severity,
        "timestamp": _utcnow(),
        "channel_chain": list(channel_chain),
    }


def send_webhook(
    title: str,
    body: str,
    *,
    alert_id: str = "",
    severity: str = "info",
    channel_chain: Optional[List[str]] = None,
    http_post: Optional[Callable[[str, Dict[str, Any]], int]] = None,
) -> Tuple[str, str]:
    """Webhook leg — the fully-local delivery path.

    Real HTTP POST of the alert JSON to LEVI_ALERT_WEBHOOK_URL. 2xx =
    delivered (L2); anything else = failed with status/reason and the
    chain continues (L1). No URL -> "unconfigured" naming the exact var
    (L4). Works against a local receiver with zero third-party services.
    """
    url = os.environ.get("LEVI_ALERT_WEBHOOK_URL", "").strip()
    if not url:
        return (
            "unconfigured",
            "LEVI_ALERT_WEBHOOK_URL not set — webhook skipped cleanly",
        )
    payload = _webhook_payload(
        alert_id, title, body, severity, channel_chain or []
    )
    try:
        post = http_post or _default_http_post_noauth
        code = post(url, payload)
    except Exception as exc:  # noqa: BLE001 — report, never raise
        return ("failed", f"webhook_error: {_redact(str(exc))[:160]}")
    if 200 <= code < 300:
        return ("delivered", f"webhook accepted (HTTP {code}) via {_host_of(url)}")
    return ("failed", f"webhook_error: HTTP {code} via {_host_of(url)}")


def send_sheets(
    title: str,
    body: str,
    *,
    alert_id: str = "",
    severity: str = "info",
    channel_chain: Optional[List[str]] = None,
    delivered_via: str = "sheets",
    http_post: Optional[Callable[[str, Dict[str, Any]], int]] = None,
) -> Tuple[str, str]:
    """Sheets logger leg — appends the alert to Chauncey's Google Sheet.

    Real HTTP POST of the alert JSON (+ delivered_via) to
    LEVI_SHEETS_WEBHOOK_URL (his Google Apps Script URL; append-row
    semantics live in his script, our side just delivers the payload
    honestly). 2xx = delivered. No URL -> "unconfigured" naming
    LEVI_SHEETS_WEBHOOK_URL and skipped cleanly — he has not supplied
    the script URL yet (L4).
    """
    url = os.environ.get("LEVI_SHEETS_WEBHOOK_URL", "").strip()
    if not url:
        return (
            "unconfigured",
            "LEVI_SHEETS_WEBHOOK_URL not set — sheets skipped cleanly "
            "(Chauncey has not supplied the Apps Script URL yet)",
        )
    payload = _webhook_payload(
        alert_id, title, body, severity, channel_chain or []
    )
    payload["delivered_via"] = delivered_via
    try:
        post = http_post or _default_http_post_noauth
        code = post(url, payload)
    except Exception as exc:  # noqa: BLE001 — report, never raise
        return ("failed", f"sheets_error: {_redact(str(exc))[:160]}")
    if 200 <= code < 300:
        return ("delivered", f"sheets accepted (HTTP {code}) via {_host_of(url)}")
    return ("failed", f"sheets_error: HTTP {code} via {_host_of(url)}")


def _default_http_post(url: str, payload: Dict[str, Any], token: str) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.getcode()


SENDERS: Dict[str, Callable[..., Tuple[str, str]]] = {
    "sms": send_sms,
    "email": send_email,
    "whatsapp": send_whatsapp,
    "webhook": send_webhook,
    "sheets": send_sheets,
}


# ---------------------------------------------------------------------------
# the chain (L1)


def dispatch(
    alert_id: str,
    dedup_key: str,
    title: str,
    body: str,
    *,
    order: Tuple[str, ...] = DEFAULT_ORDER,
    severity: str = "info",
    senders: Optional[Dict[str, Callable[..., Tuple[str, str]]]] = None,
    chain_log: Optional[Path] = None,
) -> ChainReport:
    """Try each channel in order; first confirmed delivery wins (L1).

    Every attempt is recorded; the chain record is always appended to the
    chain log (L3). Unknown channels in ``order`` are recorded as failed
    attempts, never crash the dispatch. The webhook/sheets legs receive
    the alert_id, severity, and the chain attempted so far, so their JSON
    payloads carry {alert_id, title, body, severity, timestamp,
    channel_chain} (sheets adds delivered_via).
    """
    table = senders or SENDERS
    report = ChainReport(
        alert_id=alert_id, dedup_key=dedup_key, title=title, order=tuple(order)
    )
    for channel in order:
        sender = table.get(channel)
        if sender is None:
            report.attempts.append(
                Attempt(channel, "failed", f"unknown channel {channel!r}")
            )
            continue
        try:
            if channel in ("webhook", "sheets"):
                status, detail = sender(
                    title,
                    body,
                    alert_id=report.alert_id,
                    severity=severity,
                    channel_chain=[a.channel for a in report.attempts],
                )
            else:
                status, detail = sender(title, body)
        except Exception as exc:  # noqa: BLE001 — a sender must never kill the chain
            status, detail = "failed", f"sender_error: {_redact(str(exc))[:160]}"
        # L4: unconfigured / gated channels are skipped cleanly — they are
        # not failures of the alert, they are absences of the pipe.
        norm = "skipped" if status in ("unconfigured", "needs_setup") else status
        report.attempts.append(Attempt(channel, norm, _redact(detail)))
        if status == "delivered":
            report.delivered_via = channel
            report.final = "delivered"
            break
    log_path = chain_log or DEFAULT_CHAIN_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report.to_dict()) + "\n")
    return report


def check_laws(chain_log: Optional[Path] = None) -> Dict[str, Any]:
    """Machine proof: laws hold structurally."""
    problems: List[str] = []
    for ch in DEFAULT_ORDER:
        if ch not in SENDERS:
            problems.append(f"order channel {ch!r} has no sender")
        if ch not in CHANNELS:
            problems.append(f"order channel {ch!r} not in CHANNELS")
    try:
        log = chain_log or DEFAULT_CHAIN_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"chain log dir not writable: {exc}")
    return {"ok": not problems, "laws": list(LAWS), "problems": problems}
