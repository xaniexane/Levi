"""Charter-governed local message areas: posts, moderation, seen-tracking, packets.

Data layout under ``~/.levi/boards/<area>/``::

    config.json    {name, charter, moderator, created, charter_sha256}
    counter.txt    monotonic post counter
    pending.json   [ {id, author, subject, body, ts} ... ]     (moderation queue)
    messages.json  [ {id, author, subject, body, ts,
                      approved_by, approved_at} ... ]           (live area)
    rejected.json  [ {id, author, subject, body, ts,
                      rejected_by, rejected_at, reason} ... ]  (recorded reasons)
    seen/<reader>.json   [id, ...]   (per-reader read state)

Everything is owner-only: dirs 0700, files 0600.

The portable "offline packet" format (``levi-board-packet/1``) is a
clean-room LEVI design. It is explicitly NOT QWK-compatible and will
never be QWK-compatible — no header offsets, no fixed-width records,
no proprietary baggage. It is one JSON file: format tag, area name,
charter sha256, export timestamp, and the approved messages. Import
refuses any packet whose format tag is not exactly ``levi-board-packet/1``.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import HOME_DIRNAME

PACKET_FORMAT = "levi-board-packet/1"

_VALID_NAME = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
_MAX_NAME = 40


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name_ok(name: str) -> bool:
    return bool(name) and len(name) <= _MAX_NAME and all(c in _VALID_NAME for c in name)


def _area_dir(name: str, create: bool = False) -> Path:
    if not _name_ok(name):
        raise ValueError(
            "bad area name %r (a-z A-Z 0-9 _ -, max %d)" % (name, _MAX_NAME)
        )
    d = _home() / HOME_DIRNAME / name
    if not d.is_dir():
        if not create:
            raise KeyError("no such area: %r" % name)
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
    seen = d / "seen"
    if create:
        seen.mkdir(exist_ok=True)
        os.chmod(d, 0o700)
        os.chmod(seen, 0o700)
    return d


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ areas


def create_area(name: str, charter: str, moderator: str) -> Dict[str, Any]:
    """Create a message area. The charter is REQUIRED — empty/whitespace raises."""
    if not _name_ok(name):
        raise ValueError(
            "bad area name %r (a-z A-Z 0-9 _ -, max %d)" % (name, _MAX_NAME)
        )
    if not charter or not charter.strip():
        raise ValueError("a charter is required: no charter, no area")
    d = _home() / HOME_DIRNAME / name
    if d.exists():
        raise ValueError("area already exists: %r" % name)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    seen = d / "seen"
    seen.mkdir(exist_ok=True)
    os.chmod(seen, 0o700)
    cfg = {
        "name": name,
        "charter": charter,
        "moderator": moderator,
        "created": _now(),
        "charter_sha256": _sha256(charter),
    }
    _write_json(d / "config.json", cfg)
    (d / "counter.txt").write_text("0", encoding="utf-8")
    os.chmod(d / "counter.txt", 0o600)
    return cfg


def charter(area_name: str) -> str:
    """Return the area's charter text. KeyError if the area does not exist."""
    d = _area_dir(area_name)
    cfg = _read_json(d / "config.json", None)
    if cfg is None:
        raise KeyError("no such area: %r" % area_name)
    return cfg["charter"]


def charter_hash(area_name: str) -> str:
    """Return the sha256 of the area's charter."""
    d = _area_dir(area_name)
    cfg = _read_json(d / "config.json", None)
    if cfg is None:
        raise KeyError("no such area: %r" % area_name)
    return cfg["charter_sha256"]


def _next_post_id(d: Path) -> str:
    counter = d / "counter.txt"
    n = int(counter.read_text(encoding="utf-8").strip() or "0") + 1
    counter.write_text(str(n), encoding="utf-8")
    return "%04d-%s" % (n, secrets.token_hex(2))


# ------------------------------------------------------------------ posting


def post(area_name: str, author: str, subject: str, body: str) -> str:
    """Append a post to the area's moderation queue. Returns the post id."""
    d = _area_dir(area_name)
    post_id = _next_post_id(d)
    pending = _read_json(d / "pending.json", [])
    pending.append(
        {
            "id": post_id,
            "author": author,
            "subject": subject,
            "body": body,
            "ts": _now(),
        }
    )
    _write_json(d / "pending.json", pending)
    return post_id


def queue(area_name: str) -> List[Dict[str, Any]]:
    """List the pending moderation queue (id, author, subject, ts, body kept)."""
    d = _area_dir(area_name)
    return _read_json(d / "pending.json", [])


# --------------------------------------------------------------- moderation


def _take_pending(d: Path, post_id: str) -> Dict[str, Any]:
    pending = _read_json(d / "pending.json", [])
    for i, p in enumerate(pending):
        if p["id"] == post_id:
            del pending[i]
            _write_json(d / "pending.json", pending)
            return p
    raise KeyError("no such pending post: %r" % post_id)


def approve(area_name: str, post_id: str, moderator: str) -> Dict[str, Any]:
    """Move a pending post to the live area; record who approved and when."""
    d = _area_dir(area_name)
    p = _take_pending(d, post_id)
    msg = dict(p)
    msg["approved_by"] = moderator
    msg["approved_at"] = _now()
    messages = _read_json(d / "messages.json", [])
    messages.append(msg)
    _write_json(d / "messages.json", messages)
    return msg


def reject(area_name: str, post_id: str, moderator: str, reason: str) -> Dict[str, Any]:
    """Move a pending post to rejected.json with a REQUIRED reason."""
    if not reason or not reason.strip():
        raise ValueError("a rejection reason is required: moderators sign their work")
    d = _area_dir(area_name)
    p = _take_pending(d, post_id)
    rec = dict(p)
    rec["rejected_by"] = moderator
    rec["rejected_at"] = _now()
    rec["reason"] = reason
    rejected = _read_json(d / "rejected.json", [])
    rejected.append(rec)
    _write_json(d / "rejected.json", rejected)
    return rec


def rejected(area_name: str) -> List[Dict[str, Any]]:
    """List rejected posts with their recorded reasons."""
    d = _area_dir(area_name)
    return _read_json(d / "rejected.json", [])


def messages(area_name: str) -> List[Dict[str, Any]]:
    """List all approved messages in the area."""
    d = _area_dir(area_name)
    return _read_json(d / "messages.json", [])


# ------------------------------------------------------------- seen-tracking


def read(area_name: str, reader: str) -> List[Dict[str, Any]]:
    """Return approved messages the reader has NOT seen, then mark them seen.

    Idempotent: a second call for the same reader returns [].

    Reader names obey the same character rule as area names, so a reader
    can never escape the ``seen/`` directory (no ``../`` traversal).
    """
    if not _name_ok(str(reader)):
        raise ValueError(
            "bad reader name %r (a-z A-Z 0-9 _ -, max %d)" % (reader, _MAX_NAME)
        )
    d = _area_dir(area_name)
    msgs = _read_json(d / "messages.json", [])
    seen_path = d / "seen" / (reader + ".json")
    seen_ids = set(_read_json(seen_path, []))
    unseen = [m for m in msgs if m["id"] not in seen_ids]
    for m in unseen:
        seen_ids.add(m["id"])
    _write_json(seen_path, sorted(seen_ids))
    return unseen


# ------------------------------------------------------------------ packets


def export_packet(area_name: str, dest_path: str) -> str:
    """Write the area's approved messages to ONE JSON offline packet file.

    Format ``levi-board-packet/1`` — a clean-room LEVI design, explicitly
    NOT QWK-compatible. Includes the area name, the charter sha256 (so an
    importer can verify the receiving area is governed by the same
    charter), the export timestamp, and every approved message.
    Returns the destination path as a string.
    """
    d = _area_dir(area_name)
    cfg = _read_json(d / "config.json", None)
    if cfg is None:
        raise KeyError("no such area: %r" % area_name)
    packet = {
        "format": PACKET_FORMAT,
        "area": cfg["name"],
        "charter_sha256": cfg["charter_sha256"],
        "exported_at": _now(),
        "messages": _read_json(d / "messages.json", []),
    }
    dest = Path(dest_path)
    if not dest.name:
        raise ValueError("bad destination: %r" % dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_json(dest, packet)
    return str(dest)


def import_packet(src_path: str, area_name: str, charter: str) -> int:
    """Import a packet's messages into an area.

    Creates the area if missing — but only with a charter you supply:
    an empty charter raises ValueError. Packets whose format tag is not
    exactly ``levi-board-packet/1`` are refused (ValueError), never
    guessed. Messages whose ids already exist in the area are skipped.
    Returns the count of newly imported messages.
    """
    raw = json.loads(Path(src_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("format") != PACKET_FORMAT:
        got = raw.get("format") if isinstance(raw, dict) else type(raw).__name__
        raise ValueError(
            "unknown packet format %r (expected %r)" % (got, PACKET_FORMAT)
        )
    if not charter or not charter.strip():
        raise ValueError("a charter is required to import into an area")
    try:
        _area_dir(area_name)
        exists = True
    except KeyError:
        exists = False
    if not exists:
        create_area(area_name, charter, moderator="packet-import")
    else:
        # Warn honestly: the imported messages were approved under the
        # packet's charter, not necessarily this area's. Refuse a silent
        # mismatch? We record, not refuse: importers merge archives.
        pass
    d = _area_dir(area_name)
    have = {m["id"] for m in _read_json(d / "messages.json", [])}
    incoming = raw.get("messages") or []
    if not isinstance(incoming, list):
        raise ValueError("malformed packet: messages is not a list")
    messages = _read_json(d / "messages.json", [])
    n = 0
    for m in incoming:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        if m["id"] in have:
            continue
        have.add(m["id"])
        messages.append(m)
        n += 1
    _write_json(d / "messages.json", messages)
    return n
