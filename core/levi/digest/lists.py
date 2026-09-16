"""levi.digest.lists — list storage, subscriptions, moderation, digests.

One list is one directory::

    ~/.levi/digest/<name>/
        config.json      name, owner, description, moderated, created
        members.json     list of {"email", "confirmed_at"}
        pending/         <token>.json  {"email", "created"}  (24h TTL)
        messages.json    posted messages
        hold.json        messages awaiting moderation
        rejected.json    {"message", "moderator", "reason", "rejected_at"}

Dirs are 0700, files are 0600. Writes are atomic (tmp + rename).
No network, no threads, no sleeps.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import HOME_DIRNAME

_TOKEN_TTL = timedelta(hours=24)
_EXCERPT_LEN = 240
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


# ---------------------------------------------------------------- plumbing


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _root(home: Optional[Path] = None) -> Path:
    p = (home or _home()) / HOME_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)
    return p


def _list_dir(list_name: str, home: Optional[Path] = None) -> Path:
    if not _NAME_RE.match(list_name or ""):
        raise ValueError("bad list name %r (a-z A-Z 0-9 _ -, max 40)" % (list_name,))
    p = _root(home) / list_name
    if not p.is_dir():
        raise KeyError("unknown list %r" % (list_name,))
    return p


# ---------------------------------------------------------------- lists


def create_list(
    name: str,
    owner: str,
    description: str = "",
    moderated: bool = False,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a new list. Raises ValueError on bad name or if it exists."""
    if not _NAME_RE.match(name or ""):
        raise ValueError("bad list name %r (a-z A-Z 0-9 _ -, max 40)" % (name,))
    d = _root(home) / name
    if d.exists():
        raise ValueError("list %r already exists" % (name,))
    d.mkdir(parents=True)
    os.chmod(d, 0o700)
    (d / "pending").mkdir()
    os.chmod(d / "pending", 0o700)
    config = {
        "name": name,
        "owner": owner,
        "description": description,
        "moderated": bool(moderated),
        "created": _iso(_utcnow()),
    }
    _write_json(d / "config.json", config)
    _write_json(d / "members.json", [])
    _write_json(d / "messages.json", [])
    _write_json(d / "hold.json", [])
    _write_json(d / "rejected.json", [])
    return config


def _members(d: Path) -> List[Dict[str, Any]]:
    return _read_json(d / "members.json", [])


def _pending_for(d: Path, email: str) -> List[Path]:
    out = []
    for f in (d / "pending").glob("*.json"):
        if f.stem.endswith(".tmp"):
            continue
        if _read_json(f, {}).get("email", "").lower() == email.lower():
            out.append(f)
    return out


def _email_ok(email: str) -> bool:
    local, _, domain = (email or "").partition("@")
    return bool(local) and bool(domain) and "." in domain and " " not in email


def subscribe(list_name: str, email: str, home: Optional[Path] = None) -> str:
    """Start a double-opt-in subscription; returns the confirmation token."""
    d = _list_dir(list_name, home)
    if not _email_ok(email):
        raise ValueError("bad email address %r" % (email,))
    if any(m["email"].lower() == email.lower() for m in _members(d)):
        raise ValueError("%r is already subscribed" % (email,))
    for f in _pending_for(d, email):
        f.unlink()
    token = secrets.token_hex(16)
    _write_json(
        d / "pending" / ("%s.json" % token),
        {"email": email, "created": _iso(_utcnow())},
    )
    return token


def confirm(list_name: str, token: str, home: Optional[Path] = None) -> str:
    """Confirm a subscription token. Raises ValueError on unknown/expired."""
    d = _list_dir(list_name, home)
    f = d / "pending" / ("%s.json" % token)
    if not f.is_file():
        raise ValueError("unknown or expired confirmation token")
    pending = _read_json(f, {})
    created = datetime.fromisoformat(
        pending.get("created", "1970-01-01T00:00:00+00:00")
    )
    if _utcnow() - created > _TOKEN_TTL:
        f.unlink()
        raise ValueError("confirmation token expired")
    email = pending["email"]
    members = _members(d)
    if not any(m["email"].lower() == email.lower() for m in members):
        members.append({"email": email, "confirmed_at": _iso(_utcnow())})
        _write_json(d / "members.json", members)
    f.unlink()
    return email


def unsubscribe(list_name: str, email: str, home: Optional[Path] = None) -> bool:
    """Remove a subscriber (and any pending token). True if they were a member."""
    d = _list_dir(list_name, home)
    members = _members(d)
    kept = [m for m in members if m["email"].lower() != email.lower()]
    removed = len(kept) != len(members)
    if removed:
        _write_json(d / "members.json", kept)
    for f in _pending_for(d, email):
        f.unlink()
    return removed


# ---------------------------------------------------------------- posting + moderation


def _new_message(
    sender: str, subject: str, body: str, posted_at: Optional[datetime] = None
) -> Dict[str, Any]:
    ts = posted_at or _utcnow()
    return {
        "id": secrets.token_hex(8),
        "sender": sender,
        "subject": subject,
        "body": body,
        "ts": _iso(ts),
        "status": "posted",
    }


def post(
    list_name: str,
    sender: str,
    subject: str,
    body: str,
    posted_at: Optional[datetime] = None,
    home: Optional[Path] = None,
) -> Tuple[str, str]:
    """Post to a list. Moderated lists land in the hold queue.

    Returns (msg_id, "held") or (msg_id, "posted").
    """
    d = _list_dir(list_name, home)
    config = _read_json(d / "config.json", {})
    msg = _new_message(sender, subject, body, posted_at)
    if config.get("moderated"):
        msg["status"] = "held"
        hold = _read_json(d / "hold.json", [])
        hold.append(msg)
        _write_json(d / "hold.json", hold)
        return msg["id"], "held"
    messages = _read_json(d / "messages.json", [])
    messages.append(msg)
    _write_json(d / "messages.json", messages)
    return msg["id"], "posted"


def _take_hold(d: Path, msg_id: str) -> Dict[str, Any]:
    hold = _read_json(d / "hold.json", [])
    for i, m in enumerate(hold):
        if m["id"] == msg_id:
            del hold[i]
            _write_json(d / "hold.json", hold)
            return m
    raise KeyError("no held message %r" % (msg_id,))


def approve(
    list_name: str, msg_id: str, moderator: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """Release a held message into the list archive."""
    d = _list_dir(list_name, home)
    msg = _take_hold(d, msg_id)
    msg["status"] = "posted"
    msg["approved_by"] = moderator
    msg["approved_at"] = _iso(_utcnow())
    messages = _read_json(d / "messages.json", [])
    messages.append(msg)
    _write_json(d / "messages.json", messages)
    return msg


def reject(
    list_name: str,
    msg_id: str,
    moderator: str,
    reason: str = "",
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Drop a held message into the rejection log with a reason."""
    d = _list_dir(list_name, home)
    msg = _take_hold(d, msg_id)
    msg["status"] = "rejected"
    entry = {
        "message": msg,
        "moderator": moderator,
        "reason": reason,
        "rejected_at": _iso(_utcnow()),
    }
    rejected = _read_json(d / "rejected.json", [])
    rejected.append(entry)
    _write_json(d / "rejected.json", rejected)
    return entry


# ---------------------------------------------------------------- digests + archive


def _bucket_key(ts: datetime, period: str) -> str:
    if period == "weekly":
        year, week, _ = ts.isocalendar()
        return "%d-W%02d" % (year, week)
    return ts.date().isoformat()


def compile_digest(
    list_name: str,
    period: str = "daily",
    as_of: Optional[datetime] = None,
    home: Optional[Path] = None,
) -> str:
    """Build a human-readable plain-text digest of posted messages.

    Messages are bucketed by UTC day (``daily``) or ISO week (``weekly``),
    including only messages at or before ``as_of`` (default: now).
    """
    if period not in ("daily", "weekly"):
        raise ValueError("period must be 'daily' or 'weekly', got %r" % (period,))
    d = _list_dir(list_name, home)
    cutoff = as_of or _utcnow()
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    messages = _read_json(d / "messages.json", [])
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for m in messages:
        ts = datetime.fromisoformat(m["ts"])
        if ts > cutoff:
            continue
        buckets.setdefault(_bucket_key(ts, period), []).append(m)
    lines = [
        "DIGEST: %s (%s)" % (list_name, period),
        "Messages: %d" % sum(len(v) for v in buckets.values()),
        "=" * 60,
    ]
    for key in sorted(buckets):
        lines.append("")
        lines.append("--- %s ---" % key)
        for m in sorted(buckets[key], key=lambda m: m["ts"]):
            excerpt = m["body"][:_EXCERPT_LEN]
            if len(m["body"]) > _EXCERPT_LEN:
                excerpt += "..."
            lines.append("")
            lines.append("Subject: %s" % m["subject"])
            lines.append("From: %s  |  %s" % (m["sender"], m["ts"]))
            lines.append(excerpt)
    lines.append("")
    return "\n".join(lines)


def archive_search(
    list_name: str, query: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Case-insensitive substring search over subject/body/sender of messages."""
    d = _list_dir(list_name, home)
    q = (query or "").lower()
    if not q:
        return []
    hits = []
    for m in _read_json(d / "messages.json", []):
        haystack = "%s\n%s\n%s" % (m["subject"], m["sender"], m["body"])
        if q in haystack.lower():
            hits.append(m)
    return hits
