"""The LEVI Oath daemon — unattended mission execution.

Loop: poll intake (Maildir and/or IMAP) -> build missions -> enforce the
policy gates in order (trust, permission, risk ceiling) -> enforce the
per-contact rate limit -> run the pipeline -> append everything to the
tamper-evident audit trail -> mark the mail seen.

Replies are **not** daemon I/O: auto-reply is a ``reply:`` pipeline stage,
subject to the same policy checks as every other stage.  The daemon only
provides the SMTP transport that the stage calls into, and only when the
stage authorises.

``--once`` runs a single poll cycle (for cron).  Without it, the daemon
polls every ``poll_interval`` seconds until interrupted.
"""

from __future__ import annotations

import json
import smtplib
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable, Optional

from levi.oath import USAGE_FILE
from levi.oath.audit import AuditLog
from levi.oath.commands import CommandRegistry
from levi.oath.contacts import Contact, ContactBook
from levi.oath.inbox import (
    MailConfig,
    Mission,
    load_mail_config,
    mark_seen,
    poll,
)
from levi.oath.pipeline import Pipeline, parse, run as run_pipeline
from levi.oath.policy import PolicyDecision, check_pipeline, trust_gate, trust_meets_floor
from levi.oath.trust import TRUSTED, VERIFIED

__all__ = [
    "Daemon",
    "send_mail",
    "check_rate_limit",
    "record_mission_use",
]

#: Trust levels that may create missions (the hard requirement).
MISSION_TRUST = (VERIFIED, TRUSTED)


def send_mail(
    config: MailConfig,
    to_address: str,
    subject: str,
    body: str,
    *,
    in_reply_to: str = "",
) -> None:
    """Send one email via SMTP (stdlib ``smtplib`` only).

    Raises :class:`RuntimeError` when SMTP is not configured.
    """
    if not config.smtp_host or not config.smtp_from:
        raise RuntimeError("SMTP is not configured (see mail.json)")
    msg = EmailMessage(policy=None)
    msg["From"] = config.smtp_from
    msg["To"] = to_address
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=config.smtp_from.rsplit("@", 1)[-1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg.set_content(body)
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=60) as smtp:
        smtp.ehlo()
        if config.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if config.smtp_user:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(msg)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def _load_usage() -> dict[str, list[float]]:
    try:
        data = json.loads(USAGE_FILE().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return {k: [float(t) for t in v] for k, v in data.items() if isinstance(v, list)}


def _save_usage(usage: dict[str, list[float]]) -> None:
    USAGE_FILE().parent.mkdir(parents=True, exist_ok=True)
    tmp = USAGE_FILE().with_suffix(".tmp")
    tmp.write_text(json.dumps(usage, sort_keys=True) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(USAGE_FILE())


def check_rate_limit(contact: Contact, *, now: Optional[float] = None) -> PolicyDecision:
    """Return a denial when the contact exhausted their hourly mission budget."""
    now = time.time() if now is None else now
    usage = _load_usage()
    recent = [t for t in usage.get(contact.name, []) if now - t < 3600]
    if len(recent) >= contact.max_missions_per_hour:
        return PolicyDecision(
            False,
            "rate-limit",
            f"contact {contact.name!r} exceeded {contact.max_missions_per_hour}/hour — denied",
        )
    return PolicyDecision(True, "rate-limit", "within rate limit")


def record_mission_use(contact: Contact, *, now: Optional[float] = None) -> None:
    """Record one mission against the contact's hourly budget."""
    now = time.time() if now is None else now
    usage = _load_usage()
    recent = [t for t in usage.get(contact.name, []) if now - t < 3600]
    recent.append(now)
    usage[contact.name] = recent
    _save_usage(usage)


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

class Daemon:
    """Poll intake, enforce policy, run missions, audit everything."""

    def __init__(
        self,
        *,
        book: Optional[ContactBook] = None,
        registry: Optional[CommandRegistry] = None,
        audit: Optional[AuditLog] = None,
        config: Optional[MailConfig] = None,
        poll_interval: int = 60,
        dry_run: bool = False,
        on_event: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        self.book = book or ContactBook()
        self.registry = registry or CommandRegistry()
        self.audit = audit or AuditLog()
        self.config = config or load_mail_config()
        self.poll_interval = max(5, int(poll_interval))
        self.dry_run = dry_run
        self.on_event = on_event
        self._stop = False

    # -- events ---------------------------------------------------------
    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        self.audit.append({"event": event, **payload})
        if self.on_event:
            self.on_event(event, payload)

    def stop(self) -> None:
        """Ask the poll loop to exit after the current cycle."""
        self._stop = True

    # -- one cycle --------------------------------------------------------
    def run_once(self, *, use_imap: bool = False, use_maildir: bool = True) -> dict[str, Any]:
        """Poll intake once and process every mission found.

        Returns a summary ``{"missions": n, "ran": n, "denied": n, "errors": n}``.
        """
        summary = {"missions": 0, "ran": 0, "denied": 0, "errors": 0}
        for key, mission in poll(
            self.book, use_imap=use_imap, use_maildir=use_maildir, config=self.config
        ):
            summary["missions"] += 1
            try:
                outcome = self.process_mission(mission)
            except Exception as exc:  # a mission must never kill the daemon
                self._emit("mission.error", {
                    "message_id": mission.message_id,
                    "from": mission.from_address,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                summary["errors"] += 1
                outcome = "error"
            finally:
                # The mission is recorded (or the error is); the mail is seen.
                try:
                    mark_seen(key, config=self.config)
                except Exception:
                    pass
            if outcome == "ran":
                summary["ran"] += 1
            elif outcome == "denied":
                summary["denied"] += 1
            elif outcome == "error":
                summary["errors"] += 1
        return summary

    def process_mission(self, mission: Mission) -> str:
        """Enforce the gates and run one mission.  Returns ``ran``/``denied``/``error``."""
        base = {
            "message_id": mission.message_id,
            "from": mission.from_address,
            "subject": mission.subject,
            "trust": mission.trust,
            "contact": mission.contact_name,
        }

        contact = mission.contact
        if contact is None:
            self._emit("mission.denied", {**base, "gate": "trust",
                                          "reason": "sender is not a known contact"})
            return "denied"

        # Gate 1 — trust (hard requirement, no override).
        decision = trust_gate(contact, mission.trust)
        if not decision.allowed:
            self._emit("mission.denied", {**base, "gate": decision.gate, "reason": decision.reason})
            return "denied"

        # Rate limit (before the pipeline runs).
        decision = check_rate_limit(contact)
        if not decision.allowed:
            self._emit("mission.denied", {**base, "gate": decision.gate, "reason": decision.reason})
            return "denied"

        if mission.parse_error:
            self._emit("mission.denied", {**base, "gate": "parse",
                                          "reason": f"pipeline parse error: {mission.parse_error}"})
            return "denied"

        # Gates 2+3 — per-stage permission and risk ceiling, checked before
        # each stage executes (pipeline.run re-checks per stage too).
        stages = [self._stage_from_dict(s) for s in mission.stages]
        precheck = check_pipeline(contact, mission.stages, self.registry)
        for stage_dict, dec in zip(mission.stages, precheck):
            if not dec.allowed:
                self._emit("mission.denied", {**base, "gate": dec.gate,
                                              "stage": stage_dict.get("raw", ""),
                                              "reason": dec.reason})
                return "denied"

        record_mission_use(contact)
        self._emit("mission.accepted", {**base, "stages": len(stages)})

        pipeline = Pipeline(stages=stages)
        run_pipeline(
            pipeline,
            contact,
            registry=self.registry,
            dry_run=self.dry_run,
            reply_to=mission.from_address or contact.email,
            send_reply=self._make_reply_sender(mission),
        )
        denied_stage = next((r for r in pipeline.results
                             if r.decision is not None and not r.decision.allowed), None)
        if denied_stage is not None:
            self._emit("mission.denied", {**base, "gate": denied_stage.decision.gate,
                                          "stage": denied_stage.stage.raw,
                                          "reason": denied_stage.decision.reason})
            return "denied"
        failed = next((r for r in pipeline.results if not r.ok), None)
        self._emit("mission.completed", {
            **base,
            "dry_run": self.dry_run,
            "ok": failed is None,
            "failed_stage": None if failed is None else failed.stage.raw,
            "results": pipeline.to_dict()["results"],
        })
        return "ran"

    @staticmethod
    def _stage_from_dict(data: dict[str, Any]):
        from levi.oath.pipeline import Stage
        return Stage(kind=data.get("kind", "cmd"), name=data.get("name", ""),
                     args=dict(data.get("args", {})), raw=data.get("raw", ""))

    def _make_reply_sender(self, mission: Mission):
        config = self.config

        def _send(to_address: str, subject: str, body: str) -> None:
            if self.dry_run:
                self._emit("mission.reply_preview", {
                    "message_id": mission.message_id, "to": to_address,
                    "subject": subject, "body_chars": len(body),
                })
                return
            send_mail(config, to_address, subject, body, in_reply_to=mission.message_id)

        return _send

    # -- the loop -----------------------------------------------------------
    def serve(self, *, use_imap: bool = False, use_maildir: bool = True) -> None:
        """Poll forever until :meth:`stop` is called or Ctrl-C arrives."""
        self._emit("daemon.started", {"poll_interval": self.poll_interval, "dry_run": self.dry_run})
        try:
            while not self._stop:
                summary = self.run_once(use_imap=use_imap, use_maildir=use_maildir)
                self._emit("daemon.cycle", summary)
                deadline = time.time() + self.poll_interval
                while not self._stop and time.time() < deadline:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._emit("daemon.stopped", {})
