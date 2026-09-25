"""Template-based smart replies — drafts the user approves, never auto-sent.

Honest by design: suggestions are TEMPLATE matches, not a model writing
as you. Every draft is labeled ``template-draft — NOT sent`` and lives in
``<home>/drafts.json`` until the user runs ``approve`` (which merely marks
it approved and prints it — this module never sends mail; sending is a
separate explicit act the user performs in their own mail client).

Template matching is keyword/regex based over subject + body. Default
templates cover: thanks, acknowledgement, scheduling, receipt confirmation,
decline, follow-up. Templates live in ``<home>/templates.json`` and are
user-editable; each is ``{"name", "when": {"subject_contains"|"body_contains"|"from_contains": [...]}, "body": str}``.
Placeholders: ``{sender}`` (from address), ``{subject}``, ``{first_name}``
(derived from the From display name — best effort, may be empty).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["ReplyEngine", "DEFAULT_TEMPLATES"]

DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "thanks",
        "when": {"body_contains": ["thank you", "thanks so much", "appreciate"]},
        "subject": "Re: {subject}",
        "body": ("You're very welcome!\n\n— sent from a template draft, not yet sent"),
    },
    {
        "name": "ack",
        "when": {"body_contains": ["please confirm", "let me know", "can you confirm"]},
        "subject": "Re: {subject}",
        "body": (
            "Confirmed — noted on my side.\n\n"
            "— sent from a template draft, not yet sent"
        ),
    },
    {
        "name": "schedule",
        "when": {"body_contains": ["meeting", "call", "schedule", "availability"]},
        "subject": "Re: {subject}",
        "body": (
            "Thanks for reaching out — I'm generally available weekday "
            "afternoons. Send over a couple of times that work for you and "
            "I'll confirm one.\n\n"
            "— sent from a template draft, not yet sent"
        ),
    },
    {
        "name": "receipt_ack",
        "when": {"subject_contains": ["receipt", "order confirmation", "invoice"]},
        "subject": "Re: {subject}",
        "body": ("Received — thank you.\n\n— sent from a template draft, not yet sent"),
    },
    {
        "name": "followup",
        "when": {"body_contains": ["follow up", "following up", "checking in"]},
        "subject": "Re: {subject}",
        "body": (
            "Thanks for following up — I haven't forgotten this. I'll get "
            "back to you shortly.\n\n"
            "— sent from a template draft, not yet sent"
        ),
    },
    {
        "name": "decline",
        "when": {"body_contains": ["unsubscribe", "opt out", "remove me"]},
        "subject": "Re: {subject}",
        "body": (
            "Understood — I'll take care of that.\n\n"
            "— sent from a template draft, not yet sent"
        ),
    },
]


def _first_name(from_value: str) -> str:
    name, _addr = parseaddr(from_value or "")
    name = name.strip().strip('"')
    return name.split()[0] if name else ""


def _matches(template: Dict[str, Any], rec: Dict[str, Any]) -> bool:
    when = template.get("when", {})
    for needle in when.get("subject_contains", []):
        if needle.lower() in rec.get("subject", "").lower():
            return True
    body = (rec.get("body", "") + " " + rec.get("subject", "")).lower()
    for needle in when.get("body_contains", []):
        if needle.lower() in body:
            return True
    for needle in when.get("from_contains", []):
        if needle.lower() in rec.get("from", "").lower():
            return True
    return False


class ReplyEngine:
    def __init__(self, home: Optional[Path] = None):
        from .triage import default_home

        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass
        self._tpl_path = self.home / "templates.json"
        self._drafts_path = self.home / "drafts.json"
        self.templates: List[Dict[str, Any]] = self._load_templates()
        self.drafts: Dict[str, Dict[str, Any]] = self._load_drafts()

    def _load_templates(self) -> List[Dict[str, Any]]:
        if not self._tpl_path.exists():
            self._tpl_path.write_text(
                json.dumps(DEFAULT_TEMPLATES, indent=2), encoding="utf-8"
            )
            return [dict(t) for t in DEFAULT_TEMPLATES]
        try:
            raw = json.loads(self._tpl_path.read_text(encoding="utf-8"))
            return (
                raw if isinstance(raw, list) else [dict(t) for t in DEFAULT_TEMPLATES]
            )
        except (OSError, ValueError):
            return [dict(t) for t in DEFAULT_TEMPLATES]

    def _load_drafts(self) -> Dict[str, Dict[str, Any]]:
        if not self._drafts_path.exists():
            return {}
        try:
            raw = json.loads(self._drafts_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_drafts(self) -> None:
        tmp = self._drafts_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.drafts, indent=2), encoding="utf-8")
        tmp.replace(self._drafts_path)

    def suggest(self, rec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return matching template suggestions (template name + filled body)."""
        out = []
        ctx = {
            "sender": rec.get("from", ""),
            "subject": rec.get("subject", "").removeprefix("Re: ").strip(),
            "first_name": _first_name(rec.get("from", "")),
        }
        for tpl in self.templates:
            if _matches(tpl, rec):
                try:
                    body = tpl["body"].format(**ctx)
                    subject = tpl.get("subject", "Re: {subject}").format(**ctx)
                except (KeyError, IndexError):
                    continue
                out.append(
                    {
                        "template": tpl["name"],
                        "to": rec.get("from", ""),
                        "subject": subject,
                        "body": body,
                        "label": "template-draft — NOT sent",
                        "honest_note": (
                            "Rule-based template match, not a model. "
                            "Review and edit before using."
                        ),
                    }
                )
        return out

    def save_draft(self, rec: Dict[str, Any], suggestion: Dict[str, Any]) -> str:
        draft_id = uuid.uuid4().hex[:12]
        self.drafts[draft_id] = {
            "id": draft_id,
            "message_id": rec.get("id"),
            "template": suggestion["template"],
            "to": suggestion["to"],
            "subject": suggestion["subject"],
            "body": suggestion["body"],
            "status": "draft",
            "created_at": time.time(),
        }
        self._save_drafts()
        return draft_id

    def approve(self, draft_id: str) -> Dict[str, Any]:
        """Mark a draft approved. Prints/returns it — does NOT send mail."""
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"no draft {draft_id!r}")
        draft["status"] = "approved"
        draft["approved_at"] = time.time()
        self._save_drafts()
        return draft

    def discard(self, draft_id: str) -> bool:
        if draft_id in self.drafts:
            del self.drafts[draft_id]
            self._save_drafts()
            return True
        return False

    def list_drafts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        drafts = list(self.drafts.values())
        if status:
            drafts = [d for d in drafts if d["status"] == status]
        drafts.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return drafts
