"""Read-only local mail store reader.

Supports maildir directories and mbox files via the stdlib ``mailbox``
module. The reader NEVER writes to the store: mailboxes are opened in
read-only spirit (we never call mutating methods), and all triage state
(snooze, drafts) lives in a separate home directory.

Message records are normalized dicts::

    {"id": str, "from": str, "to": str, "subject": str, "date": str,
     "date_ts": float|None, "list_unsub": bool, "body": str, "labels": [...]}

``id`` is derived deterministically (Message-ID when present, else a
SHA-256 of from+subject+date) so snooze/draft records can reference
messages without touching the store.
"""

from __future__ import annotations

import hashlib
import mailbox
import os
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

__all__ = ["MailStore", "normalize_message", "default_maildir_candidates"]


def _decode_header(value: Any) -> str:
    if value is None:
        return ""
    parts = []
    for chunk, charset in decode_header(str(value)):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def _addrs(value: Any) -> List[str]:
    return [addr.lower() for _name, addr in getaddresses([_decode_header(value)]) if addr]


def _body_text(msg) -> str:
    """Best-effort plain-text body, truncated for triage display."""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disp:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            return payload.decode(charset, errors="replace")[:4000]
                        except (LookupError, UnicodeDecodeError):
                            return payload.decode("utf-8", errors="replace")[:4000]
            return ""
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")[:4000]
            except (LookupError, UnicodeDecodeError):
                return payload.decode("utf-8", errors="replace")[:4000]
        return str(msg.get_payload() or "")[:4000]
    except Exception:
        return ""


def normalize_message(key: str, msg) -> Dict[str, Any]:
    from_addr = _addrs(msg.get("From"))
    msg_id = (_decode_header(msg.get("Message-ID")) or "").strip()
    subject = _decode_header(msg.get("Subject"))
    date_raw = _decode_header(msg.get("Date"))
    date_ts: Optional[float] = None
    try:
        if date_raw:
            date_ts = parsedate_to_datetime(date_raw).timestamp()
    except (ValueError, TypeError, OverflowError):
        date_ts = None
    list_unsub = bool(msg.get("List-Unsubscribe") or msg.get("List-ID"))
    if not msg_id:
        seed = f"{from_addr}|{subject}|{date_raw}".encode("utf-8")
        msg_id = "<levi-" + hashlib.sha256(seed).hexdigest()[:16] + ">"
    return {
        "id": msg_id,
        "key": key,
        "from": from_addr[0] if from_addr else "",
        "from_all": from_addr,
        "to": _addrs(msg.get("To")),
        "subject": subject,
        "date": date_raw,
        "date_ts": date_ts,
        "list_unsub": list_unsub,
        "body": _body_text(msg),
        "labels": [],
    }


def default_maildir_candidates() -> List[Path]:
    """Where a user's local mail usually lives (checked in order)."""
    home = Path(os.path.expanduser("~"))
    return [
        home / "Maildir",
        home / "Mail",
        home / ".mail",
        home / "mail",
    ]


class MailStore:
    """Read-only view over a maildir directory or mbox file."""

    def __init__(self, path: Optional[Path] = None):
        if path is None:
            found = next((p for p in default_maildir_candidates() if p.exists()), None)
            if found is None:
                raise FileNotFoundError(
                    "mailtriage: no local mail store found; looked in "
                    + ", ".join(str(p) for p in default_maildir_candidates())
                    + " (pass --maildir/--mbox explicitly)"
                )
            path = found
        self.path = Path(path)
        if self.path.is_dir():
            self._box = mailbox.Maildir(str(self.path), create=False)
            self.kind = "maildir"
        elif self.path.is_file():
            self._box = mailbox.mbox(str(self.path), create=False)
            self.kind = "mbox"
        else:
            raise FileNotFoundError(f"mailtriage: mail store not found: {self.path}")
        # Enforce read-only: the stdlib boxes expose mutating methods; we
        # simply never call them. Documented in the module docstring.

    def __len__(self) -> int:
        return len(self._box)

    def iter_messages(self) -> Iterator[Dict[str, Any]]:
        for key in self._box.iterkeys():
            try:
                msg = self._box[key]
            except (KeyError, ValueError):
                continue
            yield normalize_message(str(key), msg)

    def get(self, message_id: str) -> Optional[Dict[str, Any]]:
        for rec in self.iter_messages():
            if rec["id"] == message_id:
                return rec
        return None

    def close(self) -> None:
        try:
            self._box.close()
        except Exception:
            pass
