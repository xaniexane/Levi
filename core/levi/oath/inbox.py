"""Mail intake for LEVI Oath: Maildir + IMAP, stdlib only.

Flow per message:

1. Read the raw message (Maildir file or IMAP fetch).
2. Extract PGP/MIME signed parts and classify trust
   (:mod:`levi.oath.trust`).
3. Match the sender to a contact by email address, else by signing
   fingerprint.
4. Build a mission ``{contact, trust, signer, pipeline_text, stages,
   message_id, subject}`` where ``pipeline_text`` is the *verified signed
   content* — unsigned mail can never smuggle a pipeline in.

No raw shell anywhere in this module: missions carry pipeline text, and
pipelines execute only via signed command definitions (see
:mod:`levi.oath.commands` and :mod:`levi.oath.pipeline`).

IMAP/SMTP credentials live in ``<oath home>/mail.json`` (owner-written,
mode 0600)::

    {"imap": {"host": "…", "port": 993, "user": "…", "password": "…",
              "folder": "INBOX"},
     "smtp": {"host": "…", "port": 587, "user": "…", "password": "…",
              "use_tls": true, "from": "levi@example.com"}}
"""

from __future__ import annotations

import email
import email.message
import email.policy
import email.utils
import imaplib
import json
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from levi.oath import MAIL_FILE, MAILDIR
from levi.oath.contacts import Contact, ContactBook
from levi.oath.pipeline import parse
from levi.oath.trust import UNTRUSTED, UNVERIFIED, Classification, classify_message

__all__ = [
    "Mission",
    "MailConfig",
    "load_mail_config",
    "iter_maildir",
    "fetch_imap_unseen",
    "build_mission",
    "poll",
]


@dataclass
class Mission:
    """A mission request extracted from one email."""

    contact_name: Optional[str]
    contact: Optional[Contact]
    trust: str
    signer_fingerprint: Optional[str]
    signer_uid: Optional[str]
    pipeline_text: str
    stages: list[dict[str, Any]] = field(default_factory=list)
    message_id: str = ""
    subject: str = ""
    from_address: str = ""
    detail: str = ""
    parse_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_name": self.contact_name,
            "trust": self.trust,
            "signer_fingerprint": self.signer_fingerprint,
            "signer_uid": self.signer_uid,
            "pipeline_text": self.pipeline_text,
            "stages": self.stages,
            "message_id": self.message_id,
            "subject": self.subject,
            "from": self.from_address,
            "detail": self.detail,
            "parse_error": self.parse_error,
        }


@dataclass
class MailConfig:
    """IMAP/SMTP settings from ``mail.json``."""

    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MailConfig":
        imap = data.get("imap", {}) or {}
        smtp = data.get("smtp", {}) or {}
        return cls(
            imap_host=str(imap.get("host", "")),
            imap_port=int(imap.get("port", 993)),
            imap_user=str(imap.get("user", "")),
            imap_password=str(imap.get("password", "")),
            imap_folder=str(imap.get("folder", "INBOX")),
            smtp_host=str(smtp.get("host", "")),
            smtp_port=int(smtp.get("port", 587)),
            smtp_user=str(smtp.get("user", "")),
            smtp_password=str(smtp.get("password", "")),
            smtp_use_tls=bool(smtp.get("use_tls", True)),
            smtp_from=str(smtp.get("from", "")),
        )


def load_mail_config(path: Optional[Path] = None) -> MailConfig:
    """Load ``mail.json``; returns an empty config when absent."""
    path = path or MAIL_FILE()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MailConfig()
    return MailConfig.from_dict(data)


# ---------------------------------------------------------------------------
# Maildir
# ---------------------------------------------------------------------------


def iter_maildir(maildir: Optional[Path] = None) -> Iterable[tuple[str, bytes]]:
    """Yield ``(key, raw_bytes)`` for messages in ``new/`` then ``cur/``.

    Messages are *not* moved or marked seen here — the daemon does that
    after a mission is recorded, so a crash never loses mail.
    """
    base = maildir or MAILDIR()
    for sub in ("new", "cur"):
        folder = base / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                try:
                    yield f"{sub}/{path.name}", path.read_bytes()
                except OSError:
                    continue


def mark_seen_maildir(key: str, maildir: Optional[Path] = None) -> None:
    """Move a Maildir message from ``new/`` to ``cur/`` (seen)."""
    base = maildir or MAILDIR()
    sub, _, name = key.partition("/")
    if sub != "new":
        return
    src = base / "new" / name
    dst = base / "cur" / name
    if src.exists():
        (base / "cur").mkdir(parents=True, exist_ok=True)
        try:
            src.rename(dst)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# IMAP
# ---------------------------------------------------------------------------


def fetch_imap_unseen(config: MailConfig) -> list[tuple[str, bytes]]:
    """Fetch UNSEEN messages over IMAP SSL (stdlib ``imaplib``).

    Returns ``(uid, raw_bytes)`` pairs.  Messages are *not* marked
    ``\\Seen`` here — the daemon flags them after recording the mission.
    Raises :class:`RuntimeError` when IMAP is not configured.
    """
    if not config.imap_host or not config.imap_user:
        raise RuntimeError("IMAP is not configured (see mail.json)")
    context = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL(config.imap_host, config.imap_port, ssl_context=context)
    try:
        conn.login(config.imap_user, config.imap_password)
        typ, _ = conn.select(config.imap_folder, readonly=False)
        if typ != "OK":
            raise RuntimeError(f"cannot select folder {config.imap_folder!r}")
        typ, data = conn.uid("search", None, "UNSEEN")
        if typ != "OK":
            return []
        uids = (data[0] or b"").split()
        out: list[tuple[str, bytes]] = []
        for uid in uids:
            typ, fetched = conn.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not fetched:
                continue
            for part in fetched:
                if (
                    isinstance(part, tuple)
                    and len(part) == 2
                    and isinstance(part[1], bytes)
                ):
                    out.append((uid.decode("ascii", "replace"), part[1]))
                    break
        return out
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def mark_seen_imap(uid: str, config: MailConfig) -> None:
    """Flag one IMAP message ``\\Seen`` after its mission is recorded."""
    context = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL(config.imap_host, config.imap_port, ssl_context=context)
    try:
        conn.login(config.imap_user, config.imap_password)
        conn.select(config.imap_folder)
        conn.uid("store", uid, "+FLAGS", "(\\Seen)")
    finally:
        try:
            conn.logout()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Mission building
# ---------------------------------------------------------------------------


def _first_text_body(msg: email.message.Message) -> str:
    """Best-effort plain-text body for *unsigned* mail (diagnostics only)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            if (part.get_content_type() or "").lower() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode("utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload is None:
        payload = str(msg.get_payload()).encode("utf-8", "replace")
    return bytes(payload).decode("utf-8", "replace")


def _strip_clearsign_armor(text: str) -> str:
    """Remove PGP clear-sign armor, returning the signed cleartext."""
    lines = text.splitlines()
    if not any("BEGIN PGP SIGNED MESSAGE" in ln for ln in lines):
        return text
    body: list[str] = []
    in_headers = True
    past_blank = False
    for ln in lines:
        if "BEGIN PGP SIGNED MESSAGE" in ln:
            continue
        if in_headers:
            if ln.strip() == "" and not past_blank:
                past_blank = True
                in_headers = False
            continue
        if "BEGIN PGP SIGNATURE" in ln:
            break
        body.append(ln[2:] if ln.startswith("- ") else ln)
    return "\n".join(body).strip() + "\n"


def build_mission(raw: bytes, book: ContactBook) -> Mission:
    """Build a mission from one raw email.

    The pipeline text always comes from the *verified signed content*:
    unsigned mail yields an ``UNVERIFIED`` mission with no pipeline, so
    the trust gate (:mod:`levi.oath.policy`) will refuse it.
    """
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    message_id = str(msg.get("Message-ID", "") or "")
    subject = str(msg.get("Subject", "") or "")
    from_addrs = [addr for _, addr in email.utils.getaddresses(msg.get_all("From", []))]
    from_address = (from_addrs[0] if from_addrs else "").strip()

    contact = book.find_by_email(from_address) if from_address else None

    classification: Classification = classify_message(
        msg, pins=contact.fingerprints if contact else None
    )

    if classification.signer_fingerprint and contact is None:
        # The signer may be known even when the From: header is not.
        contact = book.find_by_fingerprint(classification.signer_fingerprint)

    pipeline_text = ""
    stages: list[dict[str, Any]] = []
    parse_error = ""
    if (
        classification.level not in (UNVERIFIED, UNTRUSTED)
        and classification.signed_bytes
    ):
        pipeline_text = _strip_clearsign_armor(
            classification.signed_bytes.decode("utf-8", "replace")
        )
        try:
            pipeline = parse(pipeline_text)
            stages = [s.to_dict() for s in pipeline.stages]
        except Exception as exc:
            parse_error = str(exc)

    return Mission(
        contact_name=contact.name if contact else None,
        contact=contact,
        trust=classification.level,
        signer_fingerprint=classification.signer_fingerprint,
        signer_uid=classification.signer_uid,
        pipeline_text=pipeline_text,
        stages=stages,
        message_id=message_id,
        subject=subject,
        from_address=from_address,
        detail=classification.detail,
        parse_error=parse_error,
    )


def poll(
    book: Optional[ContactBook] = None,
    *,
    use_imap: bool = False,
    use_maildir: bool = True,
    config: Optional[MailConfig] = None,
    maildir: Optional[Path] = None,
) -> list[tuple[str, Mission]]:
    """Collect missions from the configured intakes.

    Returns ``(key, mission)`` pairs.  ``key`` is ``"new/<file>"``,
    ``"cur/<file>"``, or ``"imap:<uid>"`` — pass it to
    :func:`mark_seen` once the mission is recorded.
    """
    book = book or ContactBook()
    out: list[tuple[str, Mission]] = []
    if use_maildir:
        for key, raw in iter_maildir(maildir):
            try:
                out.append((key, build_mission(raw, book)))
            except Exception as exc:  # never let one bad mail kill the poll
                out.append(
                    (
                        key,
                        Mission(
                            None,
                            None,
                            UNVERIFIED,
                            None,
                            None,
                            "",
                            detail=f"parse failure: {exc}",
                        ),
                    )
                )
    if use_imap:
        config = config or load_mail_config()
        for uid, raw in fetch_imap_unseen(config):
            try:
                out.append((f"imap:{uid}", build_mission(raw, book)))
            except Exception as exc:
                out.append(
                    (
                        f"imap:{uid}",
                        Mission(
                            None,
                            None,
                            UNVERIFIED,
                            None,
                            None,
                            "",
                            detail=f"parse failure: {exc}",
                        ),
                    )
                )
    return out


def mark_seen(
    key: str, *, config: Optional[MailConfig] = None, maildir: Optional[Path] = None
) -> None:
    """Mark an intake message seen after its mission is recorded."""
    if key.startswith("imap:"):
        mark_seen_imap(key[len("imap:") :], config or load_mail_config())
    else:
        mark_seen_maildir(key, maildir)
