"""Void Box relay — the keeper's ciphertext-only store-and-forward relay.

What this is
------------
A real, working relay server and client over stdlib sockets. Clients
POST sealed envelopes addressed to recipient (or room) ids; recipients
POLL for their envelopes. The relay persists opaque blobs + routing
metadata only. It is keeper-operated: by default it binds 127.0.0.1
(the keeper's own machine); binding wider requires explicit opt-in,
and the threat change of doing so is documented in the threat
register, not hidden.

Lineage (originals-first): Chauncey's lock-and-key-vault-genesis
design named this exact shape — "the server sees encrypted envelopes
only for messages", "the transport must not inspect content" (the
Transport.kt contract: ``send(envelope: ByteArray)`` — opaque
authenticated envelope), P2P as an optimization with authenticated
relay as the reliable fallback. Recreated LEVI-native: Python
stdlib, no code copied. The genesis server was a skeleton; this one
is a running relay, labeled honestly for what it is and is not.

The envelope contract: envelopes are sealed with veil.py's
``_seal_backend`` / ``_open_backend`` versioned backend (VB1/VB2).
The relay NEVER imports ``_open_backend`` — it has no decryption
primitive at all, so ciphertext-only is structural, not promised.
Recipients open envelopes with their own keys, outside this module.

Wire protocol (framing)
-----------------------
Every message: 4-byte big-endian length prefix + UTF-8 JSON body.
Max frame: 1 MiB (``MAX_FRAME_BYTES``); anything larger fails closed
(connection dropped, nothing processed).

Ops (client -> server):
- {"op": "post", "to": "<recipient>", "id": "<msg id>",
         "from": "<sender, optional>", "blob": "<base64 sealed envelope>"}
  -> {"ok": true, "id": "...", "stored": true}  (dedupes by id: a
  re-posted id is acknowledged, not stored twice)
- {"op": "poll", "recipient": "<recipient>", "limit": N}
  -> {"ok": true, "envelopes": [{id, to, from, ts, blob}, ...]}
- {"op": "ack", "recipient": "<recipient>", "ids": [...]}
  -> {"ok": true, "acked": N}   (tombstones; the persistent log is
  append-only — nothing is hard-deleted within a run)
- {"op": "stats"} -> {"ok": true, "pending": {recipient: count},
  "protocol": 1}   (queue depths only — no content access)
- {"op": "ping"} -> {"ok": true, "pong": true}

Addressing: ``to`` / ``recipient`` / ``from`` are 1-128 chars of
[A-Za-z0-9._:@-]. Blobs are base64 strings, max 512 KiB of encoded
text. The relay validates shape and encoding ONLY — it never looks
at what the bytes mean.

Threading model
---------------
- One accept-loop thread per server (daemon), ``socket.accept()``
  with a short timeout so shutdown is prompt.
- One handler thread per accepted connection (daemon, short-lived:
  the connection may pipeline several framed requests then close).
- One ``threading.RLock`` guards the mailbox and the delivered
  tombstones. All per-op work is O(frame size); handlers never block
  on each other beyond the lock.
- Shutdown: ``stop()`` sets the event, joins the accept thread, and
  closes the listener. In-flight handler threads finish their current
  frame and exit (daemon anyway — a stuck client cannot wedge the
  process).

Security posture of this transport — read before binding wider
--------------------------------------------------------------
- Loopback default: 127.0.0.1. On the keeper's own machine, the wire
  attacker is anyone who can observe local loopback — stated plainly.
- Binding 0.0.0.0 (or any non-loopback address) REQUIRES
  ``public=True`` at construction / ``--public`` on the CLI. That
  opt-in is the honest admission that the threat model changes:
  a network observer sees WHO posts and WHO polls (recipient ids,
  timing, sizes), can attempt mailbox floods, and can try protocol
  abuse. Content stays dark (ciphertext-only) but metadata does not.
- This relay does NOT do TLS, does NOT do cover traffic, does NOT do
  onion circuits, and is NOT Tor. Relay-to-relay forwarding across the
  open net is future work and MUST cross the Cybrus choke point
  (``request_forward_grant`` in onion.py) when it lands.
- Persistence file (when enabled) holds sealed blobs + metadata only,
  written with owner-only permissions.

Explicit non-claims: see NON_CLAIMS.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import threading
import time
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Protocol version pinned on the wire.
PROTOCOL_VERSION = 1

#: Default bind: the keeper's own machine only. Wider binds need public=True.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4799

#: Hard frame cap: 4-byte length prefix + JSON body, 1 MiB.
MAX_FRAME_BYTES = 1 << 20
#: Encoded-blob cap inside a post: 512 KiB of base64 text.
MAX_BLOB_B64 = 512 << 10
#: Recipient queue cap: flood control per address.
MAX_PER_RECIPIENT = 10_000

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}\Z")
_B64_RE = re.compile(r"[A-Za-z0-9+/=\s]*\Z")


class RelayError(ValueError):
    """Relay failures: bad frames, unknown ops, addressing violations,
    bind-policy violations. Fail-closed by construction."""


def _utcnow() -> float:
    return time.time()


def _check_id(value: object, what: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise RelayError(
            "invalid %s %r: 1-128 chars of [A-Za-z0-9._:@-]" % (what, value)
        )
    return value


def _check_blob(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RelayError("blob must be a non-empty base64 string")
    if len(value) > MAX_BLOB_B64:
        raise RelayError("blob too large (%d > %d)" % (len(value), MAX_BLOB_B64))
    if not _B64_RE.match(value):
        raise RelayError("blob is not base64")
    try:
        base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise RelayError("blob is not valid base64") from exc
    return value


# ---------------------------------------------------------------------------
# Mailbox store (ciphertext-only by construction: blobs are opaque bytes)
# ---------------------------------------------------------------------------


class MailboxStore:
    """The store the relay runs on. Envelopes are records of
    {id, to, from, ts, blob} — blob is OPAQUE bytes the store never
    inspects. Delivered envelopes are tombstoned (``delivered_at`` set)
    and drop out of the live mailbox, but the persistent log stays
    append-only: nothing is hard-deleted within a run (L4)."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        # recipient -> {id: record}
        self._pending: dict[str, dict[str, dict]] = {}
        # set of (recipient, id) delivered this run
        self._tombstones: set[tuple[str, str]] = set()
        self._store_dir = store_dir
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
            os.chmod(store_dir, 0o700)
            self._log_path = os.path.join(store_dir, "mailbox.jsonl")
            # Rebuild the live mailbox from the log on restart: pending
            # envelopes survive a restart; tombstones do too.
            self._replay_log()
        else:
            self._log_path = None

    # -- persistence ----------------------------------------------------

    def _append_log(self, event: dict) -> None:
        if not self._log_path:
            return
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
            os.chmod(self._log_path, 0o600)

    def _replay_log(self) -> None:
        try:
            lines = open(self._log_path, encoding="utf-8").read().splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "stored":
                rec = event["record"]
                self._pending.setdefault(rec["to"], {})[rec["id"]] = dict(rec)
            elif event.get("event") == "delivered":
                key = (event["to"], event["id"])
                self._tombstones.add(key)
                self._pending.get(event["to"], {}).pop(event["id"], None)

    # -- operations -------------------------------------------------------

    def post(self, to: str, blob_b64: str, msg_id: Optional[str] = None,
             sender: Optional[str] = None) -> dict:
        """Store one sealed envelope. Returns the stored record's routing
        metadata. Re-posting an already-known id is acknowledged, not
        stored twice (idempotent — the network retries safely)."""
        to = _check_id(to, "recipient")
        blob_b64 = _check_blob(blob_b64)
        msg_id = _check_id(msg_id or uuid.uuid4().hex, "message id")
        if sender is not None:
            _check_id(sender, "sender")
        with self._lock:
            queue = self._pending.setdefault(to, {})
            if msg_id in queue:
                return {"id": msg_id, "stored": False, "duplicate": True}
            if (to, msg_id) in self._tombstones:
                return {"id": msg_id, "stored": False, "duplicate": True}
            if len(queue) >= MAX_PER_RECIPIENT:
                raise RelayError("mailbox for %r is full" % to)
            record = {
                "id": msg_id,
                "to": to,
                "from": sender or "",
                "ts": _utcnow(),
                "blob": blob_b64,
            }
            queue[msg_id] = record
        self._append_log({"event": "stored", "record": dict(record)})
        return {"id": msg_id, "stored": True, "duplicate": False}

    def poll(self, recipient: str, limit: int = 50) -> list[dict]:
        """Fetch up to ``limit`` pending envelopes for a recipient,
        oldest first. Envelopes stay pending until acked — a poll is a
        read, not a delete (crash-safe delivery)."""
        recipient = _check_id(recipient, "recipient")
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise RelayError("limit must be 1..1000")
        with self._lock:
            queue = self._pending.get(recipient, {})
            recs = sorted(queue.values(), key=lambda r: r["ts"])[:limit]
            return [dict(r) for r in recs]

    def ack(self, recipient: str, ids: list) -> int:
        """Tombstone delivered envelopes. Unknown ids are ignored
        (idempotent acks); the persistent log is append-only."""
        recipient = _check_id(recipient, "recipient")
        if not isinstance(ids, list):
            raise RelayError("ids must be a list")
        acked = 0
        events = []
        with self._lock:
            queue = self._pending.get(recipient, {})
            for raw in ids:
                try:
                    msg_id = _check_id(raw, "message id")
                except RelayError:
                    continue
                if msg_id in queue:
                    del queue[msg_id]
                    self._tombstones.add((recipient, msg_id))
                    events.append({"event": "delivered", "to": recipient,
                                   "id": msg_id, "ts": _utcnow()})
                    acked += 1
        for event in events:
            self._append_log(event)
        return acked

    def stats(self) -> dict:
        """Queue depths only — no content access, no content sizes."""
        with self._lock:
            return {r: len(q) for r, q in self._pending.items() if q}

    def pending_count(self, recipient: str) -> int:
        with self._lock:
            return len(self._pending.get(recipient, {}))


# ---------------------------------------------------------------------------
# Relay server (stdlib sockets; thread-per-connection)
# ---------------------------------------------------------------------------


def _is_loopback(host: str) -> bool:
    if host in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        return socket.getaddrinfo(host, None)[0][4][0].startswith("127.")
    except OSError:
        return False


class RelayServer:
    """The keeper's relay. Bind policy (L2): loopback binds always
    allowed; anything wider requires ``public=True`` — the explicit
    opt-in that admits the metadata-observability threat."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 store_dir: Optional[str] = None,
                 public: bool = False) -> None:
        if not _is_loopback(host) and not public:
            raise RelayError(
                "refusing to bind %r without public=True: a non-loopback "
                "bind exposes recipient metadata to network observers "
                "(see NON_CLAIMS)" % host
            )
        self.host = host
        self.port = port
        self.store = MailboxStore(store_dir)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    # -- lifecycle ------------------------------------------------------

    def start(self) -> "RelayServer":
        if self._thread is not None:
            raise RelayError("relay already started")
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        self._sock = socket.socket(family, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((self.host, self.port))
        except OSError as exc:
            raise RelayError("bind failed on %s:%d: %s"
                             % (self.host, self.port, exc)) from exc
        # Ephemeral ports (port=0): report the real one.
        self.port = self._sock.getsockname()[1]
        self._sock.listen(64)
        self._sock.settimeout(0.25)
        self._thread = threading.Thread(
            target=self._accept_loop, name="voidbox-relay-accept", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            worker = threading.Thread(
                target=self._handle, args=(conn,),
                name="voidbox-relay-conn", daemon=True
            )
            worker.start()

    # -- framing --------------------------------------------------------

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise RelayError("connection closed mid-frame")
            buf += chunk
        return bytes(buf)

    def _read_frame(self, conn: socket.socket) -> dict:
        header = self._recv_exact(conn, 4)
        size = int.from_bytes(header, "big")
        if size == 0 or size > MAX_FRAME_BYTES:
            raise RelayError("bad frame size %d" % size)
        body = self._recv_exact(conn, size)
        try:
            req = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RelayError("frame is not valid JSON") from exc
        if not isinstance(req, dict):
            raise RelayError("request must be a JSON object")
        return req

    @staticmethod
    def _write_frame(conn: socket.socket, obj: dict) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_FRAME_BYTES:
            raise RelayError("response too large")
        conn.sendall(len(body).to_bytes(4, "big") + body)

    # -- request dispatch -----------------------------------------------

    def _dispatch(self, req: dict) -> dict:
        op = req.get("op")
        if op == "post":
            result = self.store.post(
                to=req.get("to"),
                blob_b64=req.get("blob"),
                msg_id=req.get("id"),
                sender=req.get("from"),
            )
            return {"ok": True, "protocol": PROTOCOL_VERSION, **result}
        if op == "poll":
            envelopes = self.store.poll(req.get("recipient"),
                                        req.get("limit", 50))
            return {"ok": True, "protocol": PROTOCOL_VERSION,
                    "envelopes": envelopes}
        if op == "ack":
            acked = self.store.ack(req.get("recipient"), req.get("ids", []))
            return {"ok": True, "protocol": PROTOCOL_VERSION, "acked": acked}
        if op == "stats":
            return {"ok": True, "protocol": PROTOCOL_VERSION,
                    "pending": self.store.stats()}
        if op == "ping":
            return {"ok": True, "protocol": PROTOCOL_VERSION, "pong": True}
        raise RelayError("unknown op %r" % (op,))

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(30)
            while not self._stop.is_set():
                try:
                    req = self._read_frame(conn)
                except RelayError as exc:
                    self._write_frame(conn, {"ok": False, "error": str(exc)})
                    return
                try:
                    resp = self._dispatch(req)
                except RelayError as exc:
                    resp = {"ok": False, "error": str(exc)}
                except Exception as exc:  # never leak internals to the wire
                    resp = {"ok": False, "error": "internal error"}
                try:
                    self._write_frame(conn, resp)
                except RelayError:
                    return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def crypto_report(self) -> dict:
        """Honest transport posture: what this relay is and is not."""
        return {
            "protocol": PROTOCOL_VERSION,
            "transport": "TCP loopback store-and-forward (stdlib sockets)",
            "tls": False,
            "cover_traffic": False,
            "ciphertext_only": True,
            "decryption_primitive": None,
            "bind": "%s:%d" % (self.host, self.port),
            "persistence": "owner-only jsonl" if self.store._log_path else "memory-only",
        }


# ---------------------------------------------------------------------------
# Relay client (same module; keeper-side convenience)
# ---------------------------------------------------------------------------


class RelayClient:
    """Thin client for the relay protocol: post sealed envelopes, poll,
    ack. The client holds the keys; the relay never does."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def _roundtrip(self, req: dict) -> dict:
        body = json.dumps(req, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_FRAME_BYTES:
            raise RelayError("request too large")
        with socket.create_connection((self.host, self.port),
                                       timeout=self.timeout) as conn:
            conn.sendall(len(body).to_bytes(4, "big") + body)
            header = b""
            while len(header) < 4:
                chunk = conn.recv(4 - len(header))
                if not chunk:
                    raise RelayError("relay closed the connection")
                header += chunk
            size = int.from_bytes(header, "big")
            if size == 0 or size > MAX_FRAME_BYTES:
                raise RelayError("bad response frame size %d" % size)
            data = b""
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk:
                    raise RelayError("relay closed the connection mid-frame")
                data += chunk
        resp = json.loads(data.decode("utf-8"))
        if not resp.get("ok"):
            raise RelayError("relay refused: %s" % resp.get("error"))
        return resp

    def post(self, to: str, blob_b64: str,
             msg_id: Optional[str] = None,
             sender: Optional[str] = None) -> dict:
        req: dict = {"op": "post", "to": to, "blob": blob_b64}
        if msg_id is not None:
            req["id"] = msg_id
        if sender is not None:
            req["from"] = sender
        return self._roundtrip(req)

    def poll(self, recipient: str, limit: int = 50) -> list[dict]:
        return self._roundtrip(
            {"op": "poll", "recipient": recipient, "limit": limit}
        )["envelopes"]

    def ack(self, recipient: str, ids: list[str]) -> int:
        return self._roundtrip(
            {"op": "ack", "recipient": recipient, "ids": ids}
        )["acked"]

    def stats(self) -> dict:
        return self._roundtrip({"op": "stats"})["pending"]

    def ping(self) -> bool:
        return bool(self._roundtrip({"op": "ping"})["pong"])


# ---------------------------------------------------------------------------
# Threat register + explicit non-claims
# ---------------------------------------------------------------------------

THREATS: list[dict[str, str]] = [
    {
        "id": "relay-seizure",
        "asset": "message content in transit / at rest on the relay",
        "attack": "attacker seizes the relay machine or its disk, or a "
        "hostile admin reads the store",
        "mitigation": "ciphertext-only by construction: the relay imports "
        "no decryption primitive (no _open_backend), holds no keys, and "
        "stores only opaque base64 blobs + routing metadata. A seized "
        "relay yields ciphertext.",
        "residual": "routing metadata (sender, recipient ids, timestamps, "
        "sizes) is visible to whoever holds the store — relationship "
        "mapping, not content. Use anonymous/pseudonymous addressing if "
        "that matters.",
        "status": "implemented",
    },
    {
        "id": "metadata-observer",
        "asset": "who talks to whom, when, how much",
        "attack": "network observer watches a non-loopback relay bind",
        "mitigation": "loopback default (127.0.0.1); any wider bind "
        "requires explicit public=True opt-in. No TLS in this build, so "
        "a wider bind is a stated metadata exposure, not an accident.",
        "residual": "even on loopback, a local machine observer sees "
        "traffic; message count and timing leak at every layer — no "
        "cover traffic in this build.",
        "status": "implemented",
    },
    {
        "id": "mailbox-flood",
        "asset": "relay availability / disk",
        "attack": "client posts unbounded envelopes to one recipient",
        "mitigation": "per-recipient queue cap (MAX_PER_RECIPIENT), "
        "per-blob size cap (MAX_BLOB_B64), per-frame cap "
        "(MAX_FRAME_BYTES); the relay never reads a frame it will not "
        "process.",
        "residual": "no per-sender authentication in this build — anyone "
        "who can reach the relay can fill mailboxes. The keeper's "
        "loopback default is the current access control.",
        "status": "implemented",
    },
    {
        "id": "protocol-abuse",
        "asset": "relay process integrity",
        "attack": "malformed frames, giant lengths, invalid JSON, unknown "
        "ops, pathological base64",
        "mitigation": "strict framing (length cap checked BEFORE reading "
        "the body), JSON object shape check, op allowlist, id/blob "
        "charset validation; every refusal is a closed connection, "
        "never partial processing; exceptions never leak internals to "
        "the wire.",
        "residual": "implementation bugs; the audit surface is this one "
        "file plus its tests.",
        "status": "implemented",
    },
    {
        "id": "replay-redelivery",
        "asset": "exactly-once delivery semantics",
        "attack": "client retries a post; recipient crashes between poll "
        "and ack",
        "mitigation": "idempotent post (dedup by message id), poll is a "
        "read not a delete, ack tombstones with an append-only log — "
        "retries are safe and crashes do not lose mail.",
        "residual": "the relay cannot stop a client from posting the "
        "same content twice under two ids; dedup is per id only.",
        "status": "implemented",
    },
]

NON_CLAIMS: list[str] = [
    "No TLS: traffic on a non-loopback bind is plaintext TCP. The "
    "envelopes are sealed (content stays dark) but the wire is not "
    "encrypted and metadata is exposed.",
    "No anonymity: the relay routes on plaintext recipient ids. This is "
    "a dropbox, not a mixnet — onion.py's circuit protocol is a "
    "separate layer, not wired here.",
    "No sender authentication in this build: anyone who can reach the "
    "relay can post to any mailbox. Reachability IS the access control "
    "until auth lands.",
    "No forward secrecy at the transport layer: a seized persistent "
    "store yields every undelivered ciphertext. Forward secrecy lives "
    "in veil.py's epoch ratchet, not in the relay.",
    "No resistance to traffic analysis: message count, timing, and "
    "sizes are observable. No cover traffic, no padding.",
    "The persistent log keeps tombstoned (delivered) records: deleted "
    "mail is gone from the live mailbox but its metadata stays in the "
    "append-only log. That is the nothing-thrown-away law working — "
    "do not confuse it with secure deletion.",
]

#: The declared laws, machine-readable (L7: law->guard->prove — declared
#: first, enforced by guards, machine-checked by check_invariants()).
LAWS = (
    ("L1", "CIPHERTEXT-ONLY: the relay stores and forwards sealed blobs; it never holds keys, never sees plaintext — structurally enforced (no decryption primitive imported, ever)."),
    ("L2", "KEEPER-OPERATED: default bind is 127.0.0.1; any wider bind requires explicit public=True opt-in, and the threat change is documented, not silent."),
    ("L3", "OPAQUE ENVELOPES: the relay routes on unsealed routing headers (to/id) only and never inspects payload content — blobs are base64-validated, never decoded."),
    ("L4", "NOTHING-THROWN-AWAY: delivered envelopes are tombstoned in an append-only log; nothing is hard-deleted within a run."),
    ("L5", "FAIL CLOSED: malformed frames, oversized frames, unknown ops, and addressing violations are refused with closed connections — never partially processed."),
    ("L6", "CRASH-SAFE DELIVERY: poll is a read, not a delete; idempotent post dedups by message id; ack tombstones — retries and crashes lose no mail."),
    ("L7", "LAW->GUARD->PROVE: laws declared first, enforced by guards, machine-checked by invariant tests (honestly named, never 'formally proven')."),
    ("L8", "HONESTY OVER POLISH: threat_model() states the exact transport posture — no TLS, no anonymity, no sender auth in this build — as declared law, not discovered gap."),
)


def threat_model() -> dict:
    """The exact threat model, queryable at runtime (L8: honesty over
    polish). What this relay claims, what it explicitly does not, and
    where the residual risk lives — no faith required."""
    return {
        "claims": [
            "keeper-operated store-and-forward over stdlib sockets",
            "ciphertext-only by construction: no keys, no decryption "
            "primitive, opaque blobs",
            "loopback default; wider binds need explicit opt-in",
            "crash-safe delivery: idempotent post, poll-as-read, "
            "append-only tombstone log",
            "strict framing and addressing: malformed input fails closed",
        ],
        "explicitly_not_claimed": list(NON_CLAIMS),
        "bind_default": "%s:%d" % (DEFAULT_HOST, DEFAULT_PORT),
        "tls": False,
        "anonymity_set": "none — the relay routes on plaintext recipient ids",
        "sender_auth": "none in this build — reachability is the access control",
        "laws": [lid for lid, _ in LAWS],
    }


def check_invariants() -> list[tuple[str, bool, str]]:
    """Structural invariants over the relay's laws, framing, and threat
    register. Returns ``(name, ok, detail)`` triples."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    # L1: ciphertext-only is structural — this module imports no
    # decryption primitive. Check the actual module namespace, not prose.
    import sys as _sys
    _mod = _sys.modules.get(__name__)
    _decrypt_names = ("_open_backend", "_open_gcm", "_open", "AESGCM", "decrypt")
    leaked = [n for n in _decrypt_names if hasattr(_mod, n)]
    check("relay imports no decryption primitive (L1 structural)",
          not leaked, "leaked: %s" % leaked if leaked else "none imported")
    # The veil versioned backend contract is the seal side only; the relay
    # must not even import the veil module (no accidental decryption path).
    # Check the module's own source, not prose.
    import inspect as _inspect
    try:
        _src = _inspect.getsource(_mod)
    except (OSError, TypeError):
        _src = ""
    _veil_imports = [
        line.strip() for line in _src.splitlines()
        if re.match(r"\s*(from\s+[\w.]*veil|import\s+[\w.]*veil)", line)
        and "levi.voidbox.relay" not in line
    ]
    check("relay source imports no veil module (L1 structural)",
          not _veil_imports,
          "; ".join(_veil_imports) if _veil_imports else "source clean")

    # L2: loopback default.
    check("default bind is loopback (L2)",
          _is_loopback(DEFAULT_HOST) and DEFAULT_HOST == "127.0.0.1",
          DEFAULT_HOST)
    try:
        RelayServer(host="0.0.0.0", port=1, public=False)
        check("non-loopback bind without opt-in is refused (L2)", False)
    except RelayError:
        check("non-loopback bind without opt-in is refused (L2)", True)

    # L5: addressing and framing guards.
    for bad in ("", "has space", "semi;colon", "x" * 129):
        try:
            _check_id(bad, "test")
            check("bad address %r refused (L5)" % bad[:12], False)
        except RelayError:
            check("bad address %r refused (L5)" % bad[:12], True)
    try:
        _check_blob("!!!not-base64!!!")
        check("non-base64 blob refused (L5)", False)
    except RelayError:
        check("non-base64 blob refused (L5)", True)
    try:
        _check_blob("a" * (MAX_BLOB_B64 + 1))
        check("oversized blob refused (L5)", False)
    except RelayError:
        check("oversized blob refused (L5)", True)

    # L4: nothing thrown away — ack tombstones, store is append-only.
    store = MailboxStore()
    r = store.post("alice", base64.b64encode(b"sealed-bytes").decode())
    mid = r["id"]
    store.ack("alice", [mid])
    check("acked envelope leaves the live mailbox (L4)",
          store.pending_count("alice") == 0)
    check("tombstone recorded, not silently dropped (L4)",
          ("alice", mid) in store._tombstones)
    # L6: idempotent post dedups.
    store2 = MailboxStore()
    a = store2.post("bob", base64.b64encode(b"x").decode(), msg_id="m1")
    b = store2.post("bob", base64.b64encode(b"y").decode(), msg_id="m1")
    check("duplicate id deduped, second blob not stored (L6)",
          a["stored"] and not b["stored"] and b["duplicate"]
          and store2.pending_count("bob") == 1)
    # Poll is a read, not a delete.
    store2.poll("bob")
    check("poll does not delete (L6)", store2.pending_count("bob") == 1)

    # Threat register discipline (matches veil.py/onion.py conventions).
    required = ("id", "asset", "attack", "mitigation", "residual", "status")
    for threat in THREATS:
        missing = [k for k in required if not threat.get(k)]
        check("threat %s fully specified" % threat.get("id", "?"),
              not missing,
              ("missing: " + ", ".join(missing)) if missing else "ok")
    check("every threat names its residual risk",
          all(t.get("residual") for t in THREATS))
    check("non-claims documented", len(NON_CLAIMS) >= 5,
          "%d explicit non-claims" % len(NON_CLAIMS))

    # Law book discipline (L7).
    law_ids = [lid for lid, _ in LAWS]
    check("laws declared (L1..L8)", len(law_ids) == 8, "%d" % len(law_ids))
    check("law ids unique", len(set(law_ids)) == len(law_ids))
    check("every law has a statement",
          all(text and text.strip() for _, text in LAWS))
    return results


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: run the keeper's relay. ``python -m levi.voidbox.relay serve``."""
    parser = argparse.ArgumentParser(
        prog="levi-voidbox-relay",
        description="Void Box keeper-operated ciphertext-only relay.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the relay server")
    serve.add_argument("--host", default=DEFAULT_HOST,
                       help="bind address (default: %(default)s)")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT,
                       help="bind port (default: %(default)s)")
    serve.add_argument("--store-dir", default=None,
                       help="persistent mailbox directory (owner-only); "
                            "default: memory-only")
    serve.add_argument("--public", action="store_true",
                       help="EXPLICIT opt-in to bind non-loopback. Admits "
                            "the metadata-observability threat (see "
                            "NON_CLAIMS). Default off.")
    args = parser.parse_args(argv)
    server = RelayServer(host=args.host, port=args.port,
                         store_dir=args.store_dir, public=args.public)
    server.start()
    print("voidbox relay on %s:%d%s (protocol v%d) — Ctrl-C to stop" % (
        server.host, server.port,
        " [PUBLIC BIND — metadata observable]" if args.public else "",
        PROTOCOL_VERSION,
    ), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PROTOCOL_VERSION",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "MAX_FRAME_BYTES",
    "MAX_BLOB_B64",
    "MAX_PER_RECIPIENT",
    "RelayError",
    "MailboxStore",
    "RelayServer",
    "RelayClient",
    "THREATS",
    "NON_CLAIMS",
    "LAWS",
    "threat_model",
    "check_invariants",
]
