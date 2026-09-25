"""Void Box alert relay — Void Box as the push channel.

Chauncey's ruling (2026-09-23): Void Box becomes the push channel for
everyone. Alerts land in a user's room/channel inside his own app — no
carrier, no Meta, no per-user setup. SMS stays as his personal fallback.

This module is the relay surface: :class:`VoidBoxRelay` posts sealed
alert frames and file-drop chunks into Void Box rooms over the existing
messenger/room infrastructure (``rooms`` seals, ``relay`` carries,
``roomsync`` keeps a second device's room state live). It never touches
the SMS path's internals — the fan-out lives in
:mod:`levi.device.alerter`'s ``drain()``, which calls this relay
best-effort alongside SMS.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — FAN-OUT COMPLETE: every alert that goes to SMS also goes to the
  relay. The alerter calls the relay for each drained item; no silent
  drops (WIRED).
- L2 — RELAY FAILURE NEVER BLOCKS SMS: relay exceptions are caught,
  counted, and logged per item; the SMS send always still runs
  (WIRED).
- L3 — UNKNOWN ROOM = HELD: rooms are addressed by registered name.
  An unregistered name raises :class:`UnknownRoomError` — never
  created implicitly, never misdelivered (WIRED).
- L4 — FILE DROPS OPT-IN: :meth:`send_file` only sends files under
  explicitly registered drop roots with explicitly allowed suffixes;
  secret-looking files (.env/.key/.pem/keys) are refused even inside
  a registered root — secrets are never auto-attached (WIRED).
- L5 — NOTHING THROWN AWAY: held and failed relay attempts go to an
  append-only relay log (owner-only), never silently dropped (WIRED).
- L6 — HONEST TRANSPORT: :func:`wiring_report` declares what is live
  against real interfaces and what runs on fakes (WIRED).

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.plaiground.gate import require_adult
from levi.voidbox.messenger.client import MessengerTransport
from levi.voidbox.relay import DEFAULT_HOST, DEFAULT_PORT
from levi.voidbox.rooms import RoomError, RoomStore

__all__ = [
    "LAWS",
    "RelayAlertsError",
    "UnknownRoomError",
    "FileNotAllowedError",
    "VoidBoxRelay",
    "make_relay_from_env",
    "wiring_report",
    "check_laws",
]

#: The declared laws, machine-readable (law->guard->prove).
LAWS = (
    ("L1", "FAN-OUT COMPLETE: every alert that goes to SMS also goes to the Void Box relay — no silent drops. (WIRED)"),
    ("L2", "RELAY FAILURE NEVER BLOCKS SMS: relay exceptions are caught, counted, logged; the SMS send still runs. (WIRED)"),
    ("L3", "UNKNOWN ROOM = HELD: rooms addressed by registered name; unknown names raise, never misdelivered. (WIRED)"),
    ("L4", "FILE DROPS OPT-IN: send_file only under registered drop roots with allowed suffixes; secrets never auto-attach. (WIRED)"),
    ("L5", "NOTHING THROWN AWAY: held/failed relay attempts go to an append-only owner-only log. (WIRED)"),
    ("L6", "HONEST TRANSPORT: wiring_report() declares live-vs-fake per capability. (WIRED)"),
)

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_REGISTRY_FILE = "relay_alerts.json"
_RELAY_LOG_FILE = "relay_alerts.log"

#: Chunk size for file drops: 192 KiB plaintext -> ~460 KiB on the
#: wire after sealing + framing + base64, comfortably under the
#: relay's 512 KiB blob cap (measured, not guessed).
CHUNK_BYTES = 192 * 1024

#: Suffixes send_file accepts out of the box (explicit allowlist, L4).
DEFAULT_ALLOWED_SUFFIXES = (
    ".zip", ".7z", ".tar.gz", ".tgz",
    ".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg",
)

#: Refused even inside a registered drop root — secrets never
#: auto-attach (L4).
DENY_SUFFIXES = (".env", ".key", ".pem", ".p12", ".pfx", ".kdbx")
DENY_NAMES = ("id_rsa", "id_ed25519", ".env")

_ALERT_BODY_MAX = 4000


class RelayAlertsError(ValueError):
    """Base error for Void Box alert-relay failures."""


class UnknownRoomError(RelayAlertsError):
    """The room name is not registered — held, never misdelivered (L3)."""


class FileNotAllowedError(RelayAlertsError):
    """The file is outside every registered drop root, has a
    disallowed suffix, or looks like a secret (L4)."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_name(value: object, what: str = "room name") -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise RelayAlertsError(
            "invalid %s %r: use 1-64 chars of [A-Za-z0-9._-]" % (what, value)
        )
    return value


def wiring_report(relay: Optional[VoidBoxRelay] = None) -> List[tuple]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability.
    Pass a relay instance to declare its live transport state (L6:
    honest transport — live-vs-fake per capability)."""
    live = False
    if relay is not None:
        from levi.voidbox.messenger import client as _c
        live = isinstance(relay.transport, _c.MessengerTransport)
    return [
        ("fanout_complete", True, "alerter drain() calls relay per item; tests prove both paths fire."),
        ("relay_failure_isolated", True, "per-item try/except; SMS path untouched on relay error."),
        ("room_registry", True, "name->room_id in owner-only relay_alerts.json; unknown names raise."),
        ("file_allowlist", True, "registered drop roots + allowed suffixes; secret denylist enforced."),
        ("relay_log", True, "append-only owner-only log of held/failed attempts."),
        ("live_delivery", True, "proven live against a real RelayServer + real RoomStores + roomsync (see tests)."),
        ("relay_transport_live", live,
         "LIVE — real MessengerTransport" if live else
         "OFFLINE — no real transport attached (fake, test, or not wired)"),
        ("remote_phone_delivery", False, "needs a running Void Box node on the phone polling the relay — not yet deployed."),
    ]


def check_laws() -> Dict[str, Any]:
    """Machine proof: the law book is complete and the guards exist."""
    problems: List[str] = []
    ids = [lid for lid, _ in LAWS]
    if ids != ["L%d" % i for i in range(1, 7)]:
        problems.append("LAWS must be L1..L6 in order")
    for name in ("send_alert", "send_file", "ensure_room", "register_room",
                 "collect", "register_drop_root"):
        if not callable(getattr(VoidBoxRelay, name, None)):
            problems.append("VoidBoxRelay.%s missing" % name)
    return {"ok": not problems, "laws": list(LAWS), "problems": problems}


def make_relay_from_env(home: Optional[Path] = None) -> Optional["VoidBoxRelay"]:
    """Build a relay from the operator's environment, or None when the
    passphrase is absent — SMS-only mode, stated honestly, never
    guessed. The passphrase is read, never logged."""
    passphrase = os.environ.get("LEVI_VOIDBOX_PASSPHRASE", "")
    if not passphrase:
        return None
    keeper_id = os.environ.get("LEVI_VOIDBOX_KEEPER", "keeper")
    host = os.environ.get("LEVI_VOIDBOX_RELAY_HOST", DEFAULT_HOST)
    port = int(os.environ.get("LEVI_VOIDBOX_RELAY_PORT", str(DEFAULT_PORT)))
    return VoidBoxRelay(
        passphrase, keeper_id, home=home, relay_host=host, relay_port=port
    )


class VoidBoxRelay:
    """The keeper's alert relay into Void Box rooms.

    ``VoidBoxRelay(passphrase, keeper_id, home=None, relay_host=...,
    relay_port=..., transport=None)`` — the passphrase unlocks the
    keeper's RoomStore (sealing happens here, on the keeper's own
    machine); ``keeper_id`` is the seal identity and must be a member
    of every room it posts to. ``transport`` is the seam: pass a fake
    in tests, omit for the real ``MessengerTransport``.

    Rooms are addressed by NAME through an explicit registry
    (``ensure_room`` / ``register_room``) — an unregistered name is
    held, never misdelivered (L3).
    """

    def __init__(
        self,
        passphrase: str,
        keeper_id: str,
        home: Optional[Path] = None,
        relay_host: str = DEFAULT_HOST,
        relay_port: int = DEFAULT_PORT,
        relay_timeout: float = 10.0,
        transport: Optional[MessengerTransport] = None,
    ) -> None:
        require_adult(home)  # FIRST, before any store is touched
        _check_name(keeper_id, "keeper_id")
        self._gate_home = home
        self.keeper_id = keeper_id
        self.rooms = RoomStore(passphrase, home=home)
        self.transport = transport or MessengerTransport(
            host=relay_host, port=relay_port, timeout=relay_timeout, home=home
        )
        base = Path(home) if home is not None else Path.home()
        self._state_dir = base / ".levi" / "voidbox"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._state_dir, 0o700)
        self._registry = self._load_registry()
        # drop_id -> {"manifest": {...}, "parts": {seq: bytes}}
        self._chunks: Dict[str, Dict[str, Any]] = {}

    # -- internal ----------------------------------------------------------

    def _require_adult(self) -> None:
        require_adult(self._gate_home)

    def _registry_path(self) -> Path:
        return self._state_dir / _REGISTRY_FILE

    def _log_path(self) -> Path:
        return self._state_dir / _RELAY_LOG_FILE

    def _load_registry(self) -> dict:
        path = self._registry_path()
        if not path.exists():
            return {"rooms": {}, "drop_roots": [],
                    "allowed_suffixes": list(DEFAULT_ALLOWED_SUFFIXES)}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise RelayAlertsError(
                "relay registry unreadable: %s" % exc) from exc
        if not isinstance(data, dict):
            raise RelayAlertsError("relay registry corrupt")
        data.setdefault("rooms", {})
        data.setdefault("drop_roots", [])
        data.setdefault("allowed_suffixes", list(DEFAULT_ALLOWED_SUFFIXES))
        return data

    def _save_registry(self) -> None:
        path = self._registry_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._registry, indent=2, sort_keys=True),
                       encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)

    def _log(self, event: str, detail: str = "") -> None:
        """Append-only relay log (L5) — never the passphrase, never keys."""
        line = json.dumps({"ts": _utcnow(), "event": event,
                           "detail": detail[:500]})
        with open(self._log_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        os.chmod(self._log_path(), 0o600)

    def _resolve_room(self, name: str) -> str:
        """Name -> room_id. Unknown names are held, never misdelivered."""
        self._require_adult()
        name = _check_name(name)
        room_id = self._registry["rooms"].get(name)
        if not room_id:
            self._log("room-held", "unknown room name %r" % name)
            raise UnknownRoomError(
                "no room registered under name %r — register it first with "
                "ensure_room() or register_room(); the alert was held, not "
                "misdelivered." % (name,)
            )
        try:
            self.rooms.get_room(room_id)
        except RoomError as exc:
            self._log("room-held", "registered room %r unreadable" % name)
            raise UnknownRoomError(
                "room %r is registered but unreadable in this store: %s — "
                "held, not misdelivered." % (name, exc)
            ) from exc
        return room_id

    def _fanout(self, room_id: str, envelope: dict) -> dict:
        """Post one sealed envelope to every active member's mailbox but
        the keeper's own (the keeper's sends are not echoed back)."""
        meta = self.rooms.get_room(room_id)
        packet = {
            "kind": "room-sealed",
            "room_id": room_id,
            "from": self.keeper_id,
            "envelope": envelope,
        }
        delivered, reports = [], []
        for member_id, m in meta["members"].items():
            if member_id == self.keeper_id or not m["active"]:
                continue
            reports.append(
                self.transport.send_packet(
                    member_id, packet, sender=self.keeper_id
                )
            )
            delivered.append(member_id)
        return {"room_id": room_id, "delivered_to": delivered,
                "relay": reports}

    @staticmethod
    def _sealed_frame(store: RoomStore, room_id: str, keeper_id: str,
                      frame: dict) -> dict:
        blob = json.dumps(frame, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
        return store.seal_message(room_id, keeper_id, blob)

    # -- rooms -------------------------------------------------------------

    def ensure_room(self, name: str) -> str:
        """Get-or-create the alert room for ``name``. Creation is the
        explicit opt-in (L3: send_alert never creates implicitly)."""
        self._require_adult()
        name = _check_name(name)
        existing = self._registry["rooms"].get(name)
        if existing:
            try:
                self.rooms.get_room(existing)
                return existing
            except RoomError:
                pass  # registered id is stale — recreate below
        meta = self.rooms.create_room("alerts-" + name, self.keeper_id)
        self._registry["rooms"][name] = meta["room_id"]
        self._save_registry()
        self._log("room-created", name)
        return meta["room_id"]

    def register_room(self, name: str, room_id: str) -> str:
        """Register an existing room under a name (e.g. one created via
        the Messenger surface)."""
        self._require_adult()
        name = _check_name(name)
        try:
            self.rooms.get_room(room_id)
        except RoomError as exc:
            raise RelayAlertsError(
                "cannot register unknown room %r: %s" % (room_id, exc)
            ) from exc
        self._registry["rooms"][name] = room_id
        self._save_registry()
        self._log("room-registered", name)
        return room_id

    def list_rooms(self) -> Dict[str, str]:
        """Registered room names -> room ids."""
        self._require_adult()
        return dict(self._registry["rooms"])

    # -- alerts ------------------------------------------------------------

    def send_alert(self, room: str, title: str, body: str = "") -> dict:
        """Seal an alert frame and fan it out to the room's members.
        Unknown room names raise :class:`UnknownRoomError` (L3)."""
        self._require_adult()
        if not isinstance(title, str) or not title.strip():
            raise RelayAlertsError("alert title must be non-empty")
        room_id = self._resolve_room(room)
        frame = {
            "type": "alert",
            "title": title.strip()[:256],
            "body": (body or "")[:_ALERT_BODY_MAX],
            "sent_at": _utcnow(),
        }
        try:
            envelope = self._sealed_frame(self.rooms, room_id,
                                          self.keeper_id, frame)
            report = self._fanout(room_id, envelope)
        except RelayAlertsError:
            raise
        except Exception as exc:
            self._log("alert-failed", "%s: %s" % (room, type(exc).__name__))
            raise RelayAlertsError(
                "relay send failed for room %r: %s" % (room, exc)) from exc
        report["title"] = frame["title"]
        return report

    # -- file drops --------------------------------------------------------

    def register_drop_root(self, path: str) -> str:
        """Allow file drops from under ``path`` (explicit opt-in, L4)."""
        self._require_adult()
        root = str(Path(path).expanduser().resolve())
        if not Path(root).is_dir():
            raise RelayAlertsError(
                "drop root %r is not a directory" % (path,))
        if root not in self._registry["drop_roots"]:
            self._registry["drop_roots"].append(root)
            self._save_registry()
            self._log("drop-root-registered", root)
        return root

    def _check_file(self, path: str) -> Path:
        """L4: the file must live under a registered drop root, carry
        an allowed suffix, and not look like a secret."""
        self._require_adult()
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise FileNotAllowedError("not a file: %r" % (path,))
        roots = [Path(r) for r in self._registry["drop_roots"]]
        if not any(p == r or r in p.parents for r in roots):
            self._log("file-held", "outside drop roots: %s" % p.name)
            raise FileNotAllowedError(
                "file %r is outside every registered drop root — register "
                "one with register_drop_root() first; held, not sent."
                % (p.name,))
        lname = p.name.lower()
        if lname in DENY_NAMES or p.suffix.lower() in DENY_SUFFIXES:
            self._log("file-held", "secret-looking file refused: %s" % p.name)
            raise FileNotAllowedError(
                "file %r looks like a secret — secrets are never "
                "auto-attached." % (p.name,))
        allowed = self._registry["allowed_suffixes"]
        ok = lname.endswith(".tar.gz") and ".tar.gz" in allowed
        ok = ok or any(lname.endswith(s) for s in allowed if s != ".tar.gz")
        if not ok:
            self._log("file-held", "suffix not allowed: %s" % p.name)
            raise FileNotAllowedError(
                "suffix of %r is not in the allowed list %s."
                % (p.name, allowed))
        return p

    def send_file(self, room: str, path: str, caption: str = "") -> dict:
        """Chunk a build artifact through the relay as sealed file-drop
        envelopes (L4 allowlist enforced). Returns the drop manifest:
        drop_id, name, size, sha256, chunks. The receiver reassembles
        with :meth:`reassemble_drop` after :meth:`collect`."""
        self._require_adult()
        room_id = self._resolve_room(room)
        p = self._check_file(path)
        raw = p.read_bytes()
        if not raw:
            raise FileNotAllowedError("file %r is empty" % (p.name,))
        drop_id = "drop_" + uuid.uuid4().hex[:16]
        digest = hashlib.sha256(raw).hexdigest()
        total = (len(raw) + CHUNK_BYTES - 1) // CHUNK_BYTES
        caption = (caption or "")[:500]
        delivered: List[str] = []
        for seq in range(total):
            chunk = raw[seq * CHUNK_BYTES:(seq + 1) * CHUNK_BYTES]
            frame = {
                "type": "file-chunk",
                "drop_id": drop_id,
                "seq": seq,
                "total": total,
                "name": p.name,
                "size": len(raw),
                "sha256": digest,
                "caption": caption,
                "sent_at": _utcnow(),
                "data_b64": base64.b64encode(chunk).decode("ascii"),
            }
            envelope = self._sealed_frame(self.rooms, room_id,
                                          self.keeper_id, frame)
            report = self._fanout(room_id, envelope)
            delivered = report["delivered_to"]
        self._log("file-sent", "%s %d chunks -> %s"
                  % (p.name, total, ",".join(delivered) or "no-members"))
        return {
            "drop_id": drop_id,
            "room": room,
            "room_id": room_id,
            "name": p.name,
            "size": len(raw),
            "sha256": digest,
            "chunks": total,
            "delivered_to": delivered,
        }

    # -- receiving ---------------------------------------------------------

    def collect(self, recipient: str, limit: int = 50) -> List[dict]:
        """Poll the recipient's mailbox, open room-sealed envelopes, and
        return parsed items: ``{"kind": "alert", ...}`` or
        ``{"kind": "file-chunk", ...}`` (chunks accumulate in
        :meth:`pending_drops` until complete). Malformed packets are
        skipped, never fatal."""
        self._require_adult()
        _check_name(recipient, "recipient")
        out: List[dict] = []
        ack_ids: List[str] = []
        for item in self.transport.fetch_packets(recipient, limit=limit):
            packet = item["packet"]
            if packet.get("kind") != "room-sealed":
                continue
            room_id = packet.get("room_id", "")
            try:
                opened = self.rooms.open_message(
                    room_id, recipient, packet["envelope"])
                frame = json.loads(bytes(opened["plaintext"]).decode("utf-8"))
            except Exception:
                continue  # one bad envelope never wedges the collect
            if not isinstance(frame, dict):
                continue
            ftype = frame.get("type")
            if ftype == "alert":
                out.append({
                    "kind": "alert",
                    "room_id": room_id,
                    "title": frame.get("title", ""),
                    "body": frame.get("body", ""),
                    "sent_at": frame.get("sent_at"),
                    "sender": opened.get("sender"),
                })
                ack_ids.append(item["id"])
            elif ftype == "file-chunk":
                self._ingest_chunk(frame)
                out.append({
                    "kind": "file-chunk",
                    "room_id": room_id,
                    "drop_id": frame.get("drop_id"),
                    "seq": frame.get("seq"),
                    "total": frame.get("total"),
                    "name": frame.get("name"),
                })
                ack_ids.append(item["id"])
        # Ack what was handled — poll is a read, ack is the delivery
        # commit; unhandled envelopes stay pending on the relay.
        if ack_ids:
            try:
                self.transport.ack(recipient, ack_ids)
            except Exception:
                pass
        return out

    def _ingest_chunk(self, frame: dict) -> None:
        drop_id = frame.get("drop_id")
        try:
            data = base64.b64decode(frame["data_b64"], validate=True)
        except Exception:
            return
        entry = self._chunks.setdefault(drop_id, {
            "manifest": {
                "drop_id": drop_id,
                "name": frame.get("name"),
                "size": frame.get("size"),
                "sha256": frame.get("sha256"),
                "caption": frame.get("caption", ""),
                "total": frame.get("total"),
            },
            "parts": {},
        })
        entry["parts"][int(frame["seq"])] = data

    def pending_drops(self) -> List[dict]:
        """Drop manifests with received/total chunk counts."""
        self._require_adult()
        return [
            {**entry["manifest"],
             "received": len(entry["parts"]),
             "complete": len(entry["parts"]) == int(entry["manifest"]["total"])}
            for entry in self._chunks.values()
        ]

    def reassemble_drop(self, drop_id: str) -> bytes:
        """Reassemble a complete drop and verify its sha256. Raises
        until every chunk has arrived; a digest mismatch raises."""
        self._require_adult()
        entry = self._chunks.get(drop_id)
        if entry is None:
            raise RelayAlertsError("unknown drop %r" % (drop_id,))
        total = int(entry["manifest"]["total"])
        parts = entry["parts"]
        if len(parts) != total:
            raise RelayAlertsError(
                "drop %r incomplete: %d/%d chunks" % (drop_id, len(parts), total))
        raw = b"".join(parts[i] for i in range(total))
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry["manifest"]["sha256"]:
            raise RelayAlertsError(
                "drop %r failed sha256 verification — refusing corrupt "
                "bytes." % (drop_id,))
        return raw

    # -- reports -----------------------------------------------------------

    def crypto_report(self) -> dict:
        """Honest posture: what this relay is and is not."""
        self._require_adult()
        return {
            "surface": "voidbox-relay-alerts (push channel)",
            "keeper_id": self.keeper_id,
            "sealing": "rooms primitive (per-room keys, replay protection)",
            "transport": "relay %s:%d (ciphertext-only store-and-forward)"
            % (self.transport.host, self.transport.port),
            "rooms_registered": len(self._registry["rooms"]),
            "drop_roots": list(self._registry["drop_roots"]),
            "non_claims": [
                "Remote phone delivery needs a running Void Box node on "
                "the phone polling the relay — not yet deployed.",
                "File drops travel as sealed chunks through the relay; "
                "very large files mean many envelopes (no streaming).",
                "The relay operator sees routing metadata (who posts, "
                "who polls, when) — same as the base relay.",
            ],
            "laws": [lid for lid, _ in LAWS],
        }
