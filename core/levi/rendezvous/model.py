"""Intent store: declared rendezvous intents with opt-in RSVP.

All state lives in one JSON document under ``~/.levi/rendezvous/``.
Directory 0700, file 0600 — the keeper's plans, never published.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import HOME_DIRNAME, RendezvousError

__all__ = [
    "RendezvousError",
    "Intent",
    "IntentStore",
    "parse_time",
]

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def parse_time(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware datetime.

    Naive values are assumed to be UTC. Raises RendezvousError on garbage —
    deny-closed, never guessed.
    """
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise RendezvousError("unparseable time %r (want ISO-8601)" % (value,)) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:48].strip("-") or "intent"


@dataclass
class Intent:
    """One declared rendezvous: who will be where, when."""

    id: str
    who: str
    where: str
    starts_at: str  # ISO-8601
    ends_at: str  # ISO-8601
    note: str = ""
    invites: List[str] = field(default_factory=list)  # suggested, never auto-added
    rsvps: Dict[str, str] = field(default_factory=dict)  # member_id -> rsvp_at ISO
    cancelled: bool = False
    cancelled_at: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Intent":
        return cls(
            id=str(d.get("id", "")),
            who=str(d.get("who", "")),
            where=str(d.get("where", "")),
            starts_at=str(d.get("starts_at", "")),
            ends_at=str(d.get("ends_at", "")),
            note=str(d.get("note", "")),
            invites=list(d.get("invites", []) or []),
            rsvps=dict(d.get("rsvps", {}) or {}),
            cancelled=bool(d.get("cancelled", False)),
            cancelled_at=str(d.get("cancelled_at", "")),
            created_at=str(d.get("created_at", "")),
        )

    def status(self, now: Optional[datetime] = None) -> str:
        """Derived, never stored: cancelled > expired > open."""
        if self.cancelled:
            return "cancelled"
        ref = now or _now()
        if parse_time(self.ends_at) <= ref:
            return "expired"
        return "open"

    def attending(self) -> List[str]:
        return sorted(self.rsvps.keys())


class IntentStore:
    """Owner-only declared-intent store."""

    def __init__(self, home: Optional[Path] = None) -> None:
        base = Path(home) if home is not None else Path.home() / ".levi"
        self._dir = base / HOME_DIRNAME
        self._file = self._dir / "intents.json"
        self._intents: Dict[str, Intent] = {}
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        if self._file.is_file():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
            for raw in data.get("intents", []):
                try:
                    intent = Intent.from_dict(raw)
                    self._intents[intent.id] = intent
                except Exception:
                    continue  # a corrupt entry never poisons the store
        self._save()

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, 0o700)
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"intents": [i.to_dict() for i in self._intents.values()]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._file)
        os.chmod(self._file, 0o600)

    # -- core -----------------------------------------------------------

    def declare(
        self,
        who: str,
        where: str,
        starts_at: str,
        ends_at: str,
        note: str = "",
        invites: Optional[List[str]] = None,
    ) -> Intent:
        """Declare an intent. Deny-closed: bad times are refused, never guessed."""
        who, where = who.strip(), where.strip()
        if not who:
            raise RendezvousError("declare requires who")
        if not where:
            raise RendezvousError("declare requires where")
        start = parse_time(starts_at)
        end = parse_time(ends_at)
        if end <= start:
            raise RendezvousError("ends_at must be after starts_at")
        iid = _slug("%s-%s-%s" % (who, where, start.strftime("%Y%m%d%H%M")))
        n = 0
        base = iid
        while iid in self._intents:
            n += 1
            iid = "%s-%d" % (base, n)
        intent = Intent(
            id=iid,
            who=who,
            where=where,
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
            note=note.strip(),
            invites=[m for m in (invites or []) if m],
        )
        self._intents[iid] = intent
        self._save()
        return intent

    def _get(self, intent_id: str) -> Intent:
        try:
            return self._intents[intent_id]
        except KeyError:
            raise RendezvousError("unknown intent %r" % (intent_id,)) from None

    def _require_open(self, intent: Intent) -> None:
        status = intent.status()
        if status != "open":
            raise RendezvousError(
                "intent %r is %s — RSVP refused" % (intent.id, status)
            )

    def rsvp(self, intent_id: str, member_id: str) -> Intent:
        """Opt-in: a person joins by their own declaration. Nobody else can add them."""
        member_id = member_id.strip()
        if not member_id:
            raise RendezvousError("rsvp requires a member id")
        intent = self._get(intent_id)
        self._require_open(intent)
        if member_id not in intent.rsvps:
            intent.rsvps[member_id] = _now_iso()
            self._save()
        return intent

    def withdraw(self, intent_id: str, member_id: str) -> Intent:
        """Withdraw an RSVP. The intent record stays; the RSVP leaves."""
        member_id = member_id.strip()
        intent = self._get(intent_id)
        self._require_open(intent)
        if member_id not in intent.rsvps:
            raise RendezvousError(
                "%r has no RSVP on intent %r" % (member_id, intent_id)
            )
        del intent.rsvps[member_id]
        self._save()
        return intent

    def cancel(self, intent_id: str) -> Intent:
        """Cancel an intent. Recorded, kept — never deleted."""
        intent = self._get(intent_id)
        if not intent.cancelled:
            intent.cancelled = True
            intent.cancelled_at = _now_iso()
            self._save()
        return intent

    def get(self, intent_id: str) -> Intent:
        return self._get(intent_id)

    def list_all(self) -> List[Intent]:
        return sorted(self._intents.values(), key=lambda i: i.starts_at)

    def list_active(self) -> List[Intent]:
        return [i for i in self.list_all() if i.status() == "open"]
