"""Sovereign mail triage: local inbox management with no scanning.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 11]
(snooze, bundles, smart reply on a local mail store with no scanning).

This is an original, from-scratch implementation for LEVI. ``MailStore``
keeps messages as plain local records — sender, subject, body, timestamp —
and never phones home, never learns from anyone else's mail, and never
"scans" anything beyond the user's own inbox for the user's own requested
operations. On top of the store:

- **Snooze**: a message leaves the inbox until a given timestamp, then
  returns automatically via ``wake_due``. Snoozed mail is simply hidden,
  never deleted.
- **Bundles**: messages group by normalized subject thread (Re:/Fwd: stripped)
  or by sender domain; ``bundle`` returns the groupings for the current
  inbox view.
- **Smart reply**: template-based drafts, chosen by explicit keyword rules
  over the subject line (acknowledgement, meeting proposal, question,
  deadline) with a neutral fallback. The rules are listed in
  ``SMART_REPLY_RULES`` — auditable, deterministic, and free of any model.
  A draft is always returned for the user to edit; nothing is ever sent.
- **Triage order**: ``triage`` ranks the visible inbox by urgency signals
  (direct address, question marks, deadline words, thread length) with the
  weights published in ``TriageWeights``.

Public surface:
- ``MailStore``: ``ingest``, ``inbox``, ``snooze`` / ``wake_due`` /
  ``unsnooze``, ``bundle``, ``smart_reply``, ``triage``, ``mark_read``.
- ``Message``, ``Draft``, ``TriageWeights``, ``TriageError``.

Honest limits: smart reply is keyword-template matching, not understanding;
urgency ranking is a heuristic and will misjudge tone. Snooze relies on the
caller's clock via ``wake_due``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/mail-triage"

_SUBJECT_PREFIX = re.compile(r"^(re|fwd|fw):\s*", re.IGNORECASE)

# Keyword rules for smart reply: (template_key, subject/body patterns).
SMART_REPLY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("acknowledge", ("thank", "thanks", "appreciate", "grateful")),
    ("meeting", ("meeting", "call", "sync", "schedule", "calendar")),
    ("question", ("?", "could you", "would you", "please advise", "question")),
    ("deadline", ("deadline", "due", "urgent", "asap", "by friday", "by monday")),
)

TEMPLATES: Dict[str, str] = {
    "acknowledge": "Thanks for this — noted, and I'll follow up shortly.",
    "meeting": "Happy to meet. A few times that work for me: {slots}. Let me know what suits you.",
    "question": "Good question — here's what I know: {answer}. I'll confirm anything I'm unsure of.",
    "deadline": "Understood, I'll treat this as time-sensitive and get back to you by {date}.",
    "neutral": "Received — I'll review this and reply properly soon.",
}


class TriageError(ValueError):
    """Raised for invalid mail operations."""


@dataclass
class Message:
    msg_id: int
    sender: str
    subject: str
    body: str
    timestamp: float
    read: bool = False
    snoozed_until: Optional[float] = None
    labels: Tuple[str, ...] = ()


@dataclass
class Draft:
    """A suggested reply. Always a draft — nothing is ever sent."""

    msg_id: int
    template_key: str
    text: str
    rule_hits: Tuple[str, ...]


@dataclass(frozen=True)
class TriageWeights:
    """Visible urgency weights. Nothing hidden."""

    unread: float = 1.0
    question_mark: float = 0.8
    deadline_word: float = 1.2
    direct_sender_bonus: float = 0.5
    thread_length: float = 0.2


_DEADLINE_WORDS = ("deadline", "urgent", "asap", "due")


class MailStore:
    """A local mail store with sovereign triage operations."""

    def __init__(
        self,
        weights: Optional[TriageWeights] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self.weights = weights if weights is not None else TriageWeights()
        self._clock = clock or time.time
        self._messages: Dict[int, Message] = {}
        self._next_id = 1

    # -- ingest / view ----------------------------------------------------
    def ingest(
        self,
        sender: str,
        subject: str,
        body: str,
        timestamp: Optional[float] = None,
        labels: Tuple[str, ...] = (),
    ) -> Message:
        msg = Message(
            msg_id=self._next_id,
            sender=sender,
            subject=subject,
            body=body,
            timestamp=timestamp if timestamp is not None else self._clock(),
            labels=labels,
        )
        self._next_id += 1
        self._messages[msg.msg_id] = msg
        return msg

    def _visible(self, msg: Message, now: float) -> bool:
        return msg.snoozed_until is None or msg.snoozed_until <= now

    def inbox(self) -> List[Message]:
        now = self._clock()
        return sorted(
            (m for m in self._messages.values() if self._visible(m, now)),
            key=lambda m: m.timestamp,
            reverse=True,
        )

    def mark_read(self, msg_id: int) -> Message:
        msg = self._get(msg_id)
        msg.read = True
        return msg

    # -- snooze -----------------------------------------------------------
    def snooze(self, msg_id: int, until: float) -> Message:
        msg = self._get(msg_id)
        if until <= self._clock():
            raise TriageError("snooze target must be in the future")
        msg.snoozed_until = until
        return msg

    def unsnooze(self, msg_id: int) -> Message:
        msg = self._get(msg_id)
        msg.snoozed_until = None
        return msg

    def wake_due(self) -> List[int]:
        """Return snoozed messages whose time has come; they rejoin the inbox."""
        now = self._clock()
        woken = [
            m.msg_id
            for m in self._messages.values()
            if m.snoozed_until is not None and m.snoozed_until <= now
        ]
        for msg_id in woken:
            self._messages[msg_id].snoozed_until = None
        return sorted(woken)

    # -- bundles ----------------------------------------------------------
    @staticmethod
    def _thread_key(subject: str) -> str:
        key = subject
        while True:
            stripped = _SUBJECT_PREFIX.sub("", key).strip()
            if stripped == key:
                return stripped.lower()
            key = stripped

    def bundle(self, by: str = "thread") -> Dict[str, List[int]]:
        """Group visible inbox messages. ``by``: 'thread' | 'sender' | 'domain'."""
        bundles: Dict[str, List[int]] = {}
        for msg in self.inbox():
            if by == "thread":
                key = self._thread_key(msg.subject)
            elif by == "sender":
                key = msg.sender.lower()
            elif by == "domain":
                key = (
                    msg.sender.split("@")[-1].lower()
                    if "@" in msg.sender
                    else msg.sender.lower()
                )
            else:
                raise TriageError(f"unknown bundle mode {by!r}")
            bundles.setdefault(key, []).append(msg.msg_id)
        return bundles

    # -- smart reply ------------------------------------------------------
    def smart_reply(self, msg_id: int) -> Draft:
        """Keyword-rule draft suggestion. Template-based, always editable."""
        msg = self._get(msg_id)
        haystack = (msg.subject + "\n" + msg.body).lower()
        hits: List[str] = []
        template_key = "neutral"
        for key, patterns in SMART_REPLY_RULES:
            if any(p in haystack for p in patterns):
                hits.append(key)
                if template_key == "neutral":
                    template_key = key
        text = TEMPLATES[template_key]
        # Fill placeholders with bracketed prompts rather than invented facts.
        text = (
            text.replace("{slots}", "[propose 2-3 times]")
            .replace("{answer}", "[your answer here]")
            .replace("{date}", "[date]")
        )
        return Draft(
            msg_id=msg_id,
            template_key=template_key,
            text=text,
            rule_hits=tuple(hits),
        )

    # -- triage -----------------------------------------------------------
    def urgency(self, msg: Message) -> float:
        w = self.weights
        score = 0.0
        if not msg.read:
            score += w.unread
        text = (msg.subject + " " + msg.body).lower()
        if "?" in msg.subject or "?" in msg.body:
            score += w.question_mark
        if any(word in text for word in _DEADLINE_WORDS):
            score += w.deadline_word
        if "@" not in msg.sender or "." not in msg.sender.split("@")[-1]:
            score += w.direct_sender_bonus  # personal/non-domain sender
        thread_len = len(self.bundle("thread").get(self._thread_key(msg.subject), []))
        score += w.thread_length * min(thread_len - 1, 5)
        return round(score, 3)

    def triage(self) -> List[Tuple[int, float]]:
        """Visible inbox as (msg_id, urgency) pairs, most urgent first."""
        return sorted(
            ((m.msg_id, self.urgency(m)) for m in self.inbox()),
            key=lambda pair: pair[1],
            reverse=True,
        )

    # -- helpers ----------------------------------------------------------
    def _get(self, msg_id: int) -> Message:
        try:
            return self._messages[msg_id]
        except KeyError as exc:
            raise TriageError(f"no message {msg_id}") from exc
