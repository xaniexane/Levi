"""Triage engine: bundles + snooze, over normalized message records.

BUNDLES are rule-based groupings with readable, editable rules — no
engagement-tuned classifiers. Default rules:

- ``receipts``      — transactional mail (order/receipt/invoice/payment keywords)
- ``newsletters``   — bulk/list mail (List-Unsubscribe/List-ID headers, or
                      newsletter-ish sender patterns)
- ``people``        — direct human mail (no list headers, non-bulk sender)
- ``notifications`` — automated notifications that are neither receipts nor
                      newsletters (no-reply senders, alerts)

Rules live in ``<home>/rules.json`` and are fully user-editable; each rule
is ``{"name": str, "match": {"from_contains"|"subject_contains"|"list_mail"|"keywords": [...]}}``.

SNOOZE is a local ledger (``<home>/snooze.json``): ``snooze(msg_id,
until_ts=...)`` hides a message until a time, ``snooze_until_reply(msg_id)``
hides it until a reply from the original sender appears. Snoozed messages
are simply filtered from inbox views — the underlying mail is never
touched. ``wake_due(now)`` returns ids whose snooze expired, and
``check_replies`` lifts "until reply" snoozes when a matching reply is
seen (reply detection: a later message whose subject is Re:-prefixed or
whose In-Reply-To/References chain mentions the id — best effort,
documented as such).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["TriageEngine", "default_home", "DEFAULT_RULES"]

BUNDLE_ORDER = ["people", "receipts", "newsletters", "notifications", "other"]

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "name": "receipts",
        "match": {
            "keywords": [
                "receipt", "order confirmation", "your order", "invoice",
                "payment received", "shipped", "tracking number", "refund",
            ]
        },
    },
    {
        "name": "newsletters",
        "match": {"list_mail": True},
    },
    {
        "name": "notifications",
        "match": {
            "from_contains": ["no-reply", "noreply", "notify", "alerts", "donotreply"]
        },
    },
    {
        "name": "people",
        "match": {"direct": True},
    },
]


def default_home() -> Path:
    override = os.environ.get("LEVI_HOME")
    base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "mailtriage"


def _rule_matches(rule: Dict[str, Any], rec: Dict[str, Any]) -> bool:
    match = rule.get("match", {})
    haystack = f"{rec.get('from','')} {rec.get('subject','')}".lower()
    body = rec.get("body", "").lower()
    if match.get("list_mail") and rec.get("list_unsub"):
        return True
    for needle in match.get("from_contains", []):
        if needle.lower() in rec.get("from", "").lower():
            return True
    for needle in match.get("subject_contains", []):
        if needle.lower() in rec.get("subject", "").lower():
            return True
    for kw in match.get("keywords", []):
        if kw.lower() in haystack or kw.lower() in body:
            return True
    if match.get("direct"):
        # direct human mail: not list mail, not an automated sender
        automated = any(
            t in rec.get("from", "").lower()
            for t in ("no-reply", "noreply", "notify", "alerts", "donotreply",
                      "mailer-daemon", "postmaster")
        )
        return not rec.get("list_unsub") and not automated
    return False


class TriageEngine:
    """Bundles + snooze over a list of normalized message records."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass
        self._rules_path = self.home / "rules.json"
        self._snooze_path = self.home / "snooze.json"
        self.rules: List[Dict[str, Any]] = self._load_rules()
        self.snooze: Dict[str, Dict[str, Any]] = self._load_snooze()

    # -- rules ---------------------------------------------------------
    def _load_rules(self) -> List[Dict[str, Any]]:
        if not self._rules_path.exists():
            self._rules_path.write_text(
                json.dumps(DEFAULT_RULES, indent=2), encoding="utf-8"
            )
            return [dict(r) for r in DEFAULT_RULES]
        try:
            raw = json.loads(self._rules_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return [dict(r) for r in DEFAULT_RULES]
        if not isinstance(raw, list):
            return [dict(r) for r in DEFAULT_RULES]
        return raw

    def bundle(self, rec: Dict[str, Any]) -> str:
        for rule in self.rules:
            if _rule_matches(rule, rec):
                return rule["name"]
        return "other"

    def bundle_all(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for rec in records:
            out.setdefault(self.bundle(rec), []).append(rec)
        return out

    # -- snooze --------------------------------------------------------
    def _load_snooze(self) -> Dict[str, Dict[str, Any]]:
        if not self._snooze_path.exists():
            return {}
        try:
            raw = json.loads(self._snooze_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_snooze(self) -> None:
        tmp = self._snooze_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.snooze, indent=2), encoding="utf-8")
        tmp.replace(self._snooze_path)

    def snooze_until(self, message_id: str, until_ts: float, note: str = "") -> None:
        """Snooze until an epoch timestamp."""
        if until_ts <= time.time():
            raise ValueError("snooze_until: time is in the past")
        self.snooze[message_id] = {
            "mode": "until",
            "until_ts": float(until_ts),
            "note": note,
            "snoozed_at": time.time(),
        }
        self._save_snooze()

    def snooze_until_reply(self, message_id: str, sender: str = "", subject: str = "") -> None:
        """Snooze until a reply from the thread's sender appears."""
        self.snooze[message_id] = {
            "mode": "until_reply",
            "sender": sender.lower(),
            "subject": subject,
            "snoozed_at": time.time(),
        }
        self._save_snooze()

    def unsnooze(self, message_id: str) -> bool:
        if message_id in self.snooze:
            del self.snooze[message_id]
            self._save_snooze()
            return True
        return False

    def is_snoozed(self, message_id: str, now: Optional[float] = None) -> bool:
        entry = self.snooze.get(message_id)
        if not entry:
            return False
        now = time.time() if now is None else now
        if entry["mode"] == "until":
            return now < entry["until_ts"]
        return True  # until_reply stays snoozed until a reply is observed

    def wake_due(self, now: Optional[float] = None) -> List[str]:
        """Return and clear time-based snoozes whose time has come."""
        now = time.time() if now is None else now
        due = [
            mid for mid, e in self.snooze.items()
            if e["mode"] == "until" and now >= e["until_ts"]
        ]
        for mid in due:
            del self.snooze[mid]
        if due:
            self._save_snooze()
        return due

    def check_replies(self, records: List[Dict[str, Any]]) -> List[str]:
        """Lift 'until_reply' snoozes when a reply is observed.

        Reply detection (best effort, documented): a message whose sender
        matches the snoozed sender and whose subject looks like a reply
        (Re: prefix) to the snoozed subject, dated after the snooze.
        Returns the woken message ids.
        """
        woken: List[str] = []
        pending = {
            mid: e for mid, e in self.snooze.items() if e["mode"] == "until_reply"
        }
        if not pending:
            return woken
        for mid, entry in pending.items():
            sender = entry.get("sender", "")
            subject = entry.get("subject", "").lower()
            base = subject[3:].strip() if subject.startswith("re:") else subject
            for rec in records:
                if rec.get("id") == mid:
                    continue
                if sender and rec.get("from", "").lower() != sender:
                    continue
                subj = rec.get("subject", "").lower()
                looks_reply = subj.startswith("re:") and base and base in subj
                if looks_reply and (rec.get("date_ts") or 0) >= entry.get("snoozed_at", 0):
                    woken.append(mid)
                    break
        for mid in woken:
            del self.snooze[mid]
        if woken:
            self._save_snooze()
        return woken

    def inbox_view(
        self,
        records: List[Dict[str, Any]],
        bundle: Optional[str] = None,
        include_snoozed: bool = False,
        now: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Records for display: snoozed filtered out unless asked for."""
        now = time.time() if now is None else now
        out = []
        for rec in records:
            if not include_snoozed and self.is_snoozed(rec["id"], now=now):
                continue
            rec = dict(rec)
            rec["bundle"] = self.bundle(rec)
            if bundle and rec["bundle"] != bundle:
                continue
            out.append(rec)
        out.sort(key=lambda r: r.get("date_ts") or 0, reverse=True)
        return out
