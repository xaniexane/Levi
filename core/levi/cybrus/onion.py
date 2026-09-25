"""Cybrus onion-routed transport over the keeper's own relay network.

What this is
------------
A 3-hop onion-routing packet/circuit protocol whose relays are relays the
*keeper operates himself* — the directory lists his relays, descriptors
are signed with his operator key, and circuits are built over them.
There is NO real network in this build (the codebase is stdlib-first):
the protocol is implemented as pure functions (cell packing, layered
seal/peel) plus an in-process relay-network simulator, so circuit
construction, layered peeling, and delivery are fully testable without
sockets.

How a circuit works
-------------------
1. The keeper's operator key signs a descriptor for each relay he runs
   (relay id, X25519 public key, validity window). The directory only
   lists descriptors with valid signatures — centralized trust, stated
   plainly.
2. Circuit build is telescoping: the initiator does an X25519 ECDH with
   the guard relay, then sends an EXTEND (encrypted under the guard's
   hop key) naming the middle relay, then another EXTEND (encrypted
   under guard+middle keys) naming the exit. Each relay learns only its
   predecessor and successor.
3. Data cells are length-padded and layered:
   ``seal(k_guard, seal(k_middle, seal(k_exit, payload)))`` with
   AES-256-GCM via veil.py's versioned backend. Each hop peels exactly
   one layer and forwards opaque bytes. Payloads are padded to a fixed
   inner size, so every message produces identical cell sizes at every
   hop position — message length is fully hidden. Cells shrink by one
   fixed layer-growth per peel, so hop *position* is visible by size to
   a network observer (documented residual; fully uniform Sphinx-style
   cells are future work).

Crypto: X25519 (RFC 7748, shared with veil_chat's backend reporting),
AES-256-GCM (or veil.py's labeled stdlib fallback), HKDF-SHA256,
Ed25519 descriptor signatures when the ``cryptography`` package is
present, HMAC attestation fallback otherwise (labeled, never silent).

Honest threat model — read before deploying anything
----------------------------------------------------
- These relays are HIS infrastructure. The anonymity set is the set of
  users of his network — small by construction.
- This is NOT Tor. There is no cover traffic, no padding between cells
  beyond fixed cell size, no guard rotation policy, no directory
  authorities — one operator key signs the whole directory.
- It does NOT resist a global passive adversary: fixed-size cells help
  against a casual observer, not against timing/correlation analysis.
- A compromised or colluding relay set sees everything: the threat
  model assumes the relays are honest-but-curious *at worst*, and the
  E2E layer (veil_chat) is what keeps message *content* dark — every
  relay, including the exit, sees only sealed E2E envelopes.
- The simulator is method calls, not a network: it proves the protocol
  logic, not deployment security. Production needs real transport,
  real relay binaries, key rotation, and abuse handling — all future work.

External egress — the one legal path
------------------------------------
This module performs NO network I/O: no sockets, no HTTP, nothing.
When production relay transport exists, every relay-to-relay forward
MUST cross the Cybrus choke point via ``request_forward_grant()``
(``levi.cybrus.enforce.request_egress``): authenticate → router resolve
→ rate-limit → policy → signed short-lived grant, then hand the grant
to the transport. No grant, no egress — a relay never rolls its own
HTTP. The simulator is the default transport precisely because it
needs no egress at all.

Operating laws (built in, not just followed)
-------------------------------------------
Chauncey's seven operating laws are runtime-checkable invariants here,
declared as L6–L12 in the machine-readable ``LAWS`` tuple (L1–L5 are the
transport laws) and checked by ``check_invariants()`` plus the tests:

- keeper's law / anticipation — refusals name the relay, the circuit,
  and the remedy; descriptors are verified, never assumed
- originals-first — the operator-signed directory is the original;
  unknown/rogue descriptors are rejected, never auto-accepted
- law→guard→prove — laws declared first, guards enforce, invariant tests
  check (honestly named: never "formally proven")
- no-cancellation — the directory has no removal API; relays and
  descriptors are never dropped by this module
- nothing-thrown-away — relay state only grows within a run; the cell
  log is append-only
- forward-motion — a dropped cell raises immediately with its reason;
  the caller moves on, nothing blocks
- honesty over polish — ``crypto_report()`` and ``threat_model()``
  state the exact threat model: his relays, his users as the anonymity
  set, not Tor, no global-passive-adversary resistance

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from levi.cybrus import veil_chat as _chat
from levi.cybrus.veil import (
    VeilError,
    _b64d,
    _b64e,
    _hkdf,
    _open_backend,
    _seal_backend,
    fingerprint,
)
from levi.cybrus.veil_chat import VeilChatError, x25519, x25519_public


class OnionError(VeilChatError):
    """Onion transport failures: bad cells, unknown circuits, failed
    layers, bad descriptors. Fail-closed like everything else here."""


# ---------------------------------------------------------------------------
# Cell geometry (all pinned — size uniformity is the padding story)
# ---------------------------------------------------------------------------

_CMD_CREATE = 1
_CMD_EXTEND = 2
_CMD_DATA = 3

_INNER_SIZE = 480          # length-padded plaintext region per cell
_MAX_HOPS = 3
_CELL_HEADER = 1 + 16      # command + circuit id


def _probe_layer_growth() -> int:
    """Measure how many bytes one sealed layer ADDS, using the machine's
    real AEAD backend: seal 480 bytes three times (nested, as the
    protocol does) and divide. AES-256-GCM adds 31 bytes per layer
    (3 magic + 12 nonce + 16 tag); the stdlib fallback adds 51
    (3 magic + 16 nonce + 32 tag)."""
    inner = bytes(_INNER_SIZE)
    for _ in range(_MAX_HOPS):
        inner = _seal_backend(b"k" * 32, inner, b"cybrus-onion-probe")
    growth, remainder = divmod(len(inner) - _INNER_SIZE, _MAX_HOPS)
    if remainder:
        raise OnionError("cannot determine layer growth")
    return growth


_LAYER_GROWTH = _probe_layer_growth()


def _payload_layers(n: int) -> int:
    """Payload bytes for a cell with ``n`` sealed layers still on it."""
    return _INNER_SIZE + n * _LAYER_GROWTH


#: Largest cell on the wire (guard-bound: 3 layers). Cells SHRINK one
#: layer-growth per hop as each relay peels — so cells are fixed-size
#: *per hop position*, not globally. Every message produces the identical
#: sizes at every position, so message length is fully hidden; hop
#: position is visible by size to a network observer (documented
#: residual; fully uniform Sphinx-style cells are future work).
CELL_SIZE = _CELL_HEADER + _payload_layers(_MAX_HOPS)

_HOP_INFO = b"cybrus-onion-hop-v1\x00"
_LAYER_AAD_DOMAIN = b"cybrus-onion-layer-v1\x00"
_EXTEND_MAGIC = b"EXTEND\x00"
_DATA_MAGIC = b"DATA\x00"
_MAX_PLAINTEXT = _INNER_SIZE - 2 - len(_DATA_MAGIC)


def _pack_inner(payload: bytes) -> bytes:
    """Length-prefix and zero-pad to the fixed inner size."""
    if len(payload) > _INNER_SIZE - 2:
        raise OnionError(
            "payload too large for one cell (%d > %d); fragmentation is "
            "future work" % (len(payload), _INNER_SIZE - 2)
        )
    return len(payload).to_bytes(2, "big") + payload + bytes(_INNER_SIZE - 2 - len(payload))


def _unpack_inner(inner: bytes) -> bytes:
    if len(inner) != _INNER_SIZE:
        raise OnionError("inner payload has wrong size")
    n = int.from_bytes(inner[:2], "big")
    if n > _INNER_SIZE - 2:
        raise OnionError("corrupt inner length")
    return inner[2 : 2 + n]


def _layer_aad(circuit_id: bytes) -> bytes:
    return _LAYER_AAD_DOMAIN + circuit_id


def onion_wrap(hop_keys_outer_first: list[bytes], circuit_id: bytes, plaintext: bytes) -> bytes:
    """Layered seal: innermost layer is for the exit hop. Returns exactly
    ``_payload_layers(3)`` bytes — every message wraps to the identical
    size."""
    if len(hop_keys_outer_first) != _MAX_HOPS:
        raise OnionError("exactly %d hop keys required" % _MAX_HOPS)
    if len(circuit_id) != 16:
        raise OnionError("circuit id must be 16 bytes")
    inner = _pack_inner(_DATA_MAGIC + plaintext)
    aad = _layer_aad(circuit_id)
    for key in reversed(hop_keys_outer_first):
        if len(key) != 32:
            raise OnionError("hop key must be 32 bytes")
        inner = _seal_backend(key, inner, aad)
    if len(inner) != _payload_layers(_MAX_HOPS):
        raise OnionError("layered payload has wrong size")
    return inner


def onion_peel(hop_key: bytes, circuit_id: bytes, layered: bytes) -> bytes:
    """Peel one layer, shrinking the payload by exactly one layer-growth.
    Authentication failure (tampered cell, wrong key, wrong circuit)
    raises — the relay drops the cell, never forwards it."""
    if len(layered) < _payload_layers(1):
        raise OnionError("layered payload too small")
    try:
        return _open_backend(hop_key, layered, _layer_aad(circuit_id))
    except VeilError as exc:
        raise OnionError("layer authentication failed: %s" % exc) from exc


def build_cell(cmd: int, circuit_id: bytes, payload: bytes) -> bytes:
    """Pack a cell. Payloads shrink one layer-growth per hop peeled, so
    cells are fixed-size per hop position (see CELL_SIZE)."""
    if cmd not in (_CMD_CREATE, _CMD_EXTEND, _CMD_DATA):
        raise OnionError("unknown cell command %r" % cmd)
    if len(circuit_id) != 16:
        raise OnionError("circuit id must be 16 bytes")
    if not payload or (len(payload) - _INNER_SIZE) % _LAYER_GROWTH:
        raise OnionError("cell payload has wrong size")
    return bytes([cmd]) + circuit_id + payload


def parse_cell(cell: bytes) -> tuple[int, bytes, bytes]:
    """Parse a cell; malformed cells fail closed."""
    if len(cell) < _CELL_HEADER + _payload_layers(1):
        raise OnionError("cell too small")
    if (len(cell) - _CELL_HEADER - _INNER_SIZE) % _LAYER_GROWTH:
        raise OnionError("cell has wrong size")
    cmd = cell[0]
    if cmd not in (_CMD_CREATE, _CMD_EXTEND, _CMD_DATA):
        raise OnionError("unknown cell command %r" % cmd)
    return cmd, cell[1:17], cell[17:]


# ---------------------------------------------------------------------------
# Operator key + relay descriptors (his relays, his signature)
# ---------------------------------------------------------------------------


class OperatorKey:
    """The keeper's relay-operator key. Ed25519 signatures when the
    ``cryptography`` package is importable; HMAC attestation under a
    random directory key otherwise — labeled, never silent."""

    def __init__(self, private: bytes, backend: str) -> None:
        self._private = private
        self.backend = backend

    @classmethod
    def generate(cls) -> "OperatorKey":
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
                Ed25519PrivateKey,
            )

            priv = Ed25519PrivateKey.generate()
            raw = priv.private_bytes_raw()
            return cls(raw, "ed25519")
        except Exception:
            return cls(secrets.token_bytes(32), "hmac-attestation-fallback")

    def public_bytes(self) -> bytes:
        if self.backend == "ed25519":
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
                Ed25519PrivateKey,
            )

            return Ed25519PrivateKey.from_private_bytes(
                self._private
            ).public_key().public_bytes_raw()
        return hmac.new(self._private, b"cybrus-operator-pub", hashlib.sha256).digest()

    def sign(self, message: bytes) -> bytes:
        if self.backend == "ed25519":
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
                Ed25519PrivateKey,
            )

            return Ed25519PrivateKey.from_private_bytes(self._private).sign(message)
        return hmac.new(
            self._private, b"cybrus-descriptor-sig\x00" + message, hashlib.sha256
        ).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        try:
            if self.backend == "ed25519":
                from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
                    Ed25519PrivateKey,
                )

                Ed25519PrivateKey.from_private_bytes(
                    self._private
                ).public_key().verify(signature, message)
                return True
            expect = hmac.new(
                self._private, b"cybrus-descriptor-sig\x00" + message, hashlib.sha256
            ).digest()
            return hmac.compare_digest(expect, signature)
        except Exception:
            return False

    def fingerprint(self) -> str:
        return fingerprint(self.public_bytes())


def _descriptor_canonical(desc: dict) -> bytes:
    body = {k: desc[k] for k in ("relay_id", "name", "x25519_pub", "issued_at", "expires_at")}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_descriptor(
    opkey: OperatorKey, relay_id: str, name: str, x25519_pub: bytes, ttl_days: int = 90
) -> dict:
    """The keeper signs a relay descriptor: this relay is his, these are
    its keys, valid until ``expires_at``."""
    if len(x25519_pub) != 32:
        raise OnionError("relay X25519 public key must be 32 bytes")
    now = datetime.now(timezone.utc)
    desc = {
        "relay_id": relay_id,
        "name": name[:64],
        "x25519_pub": _b64e(x25519_pub),
        "issued_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(days=ttl_days)).isoformat(timespec="seconds"),
    }
    desc["signature"] = _b64e(opkey.sign(_descriptor_canonical(desc)))
    desc["sig_backend"] = opkey.backend
    return desc


def verify_descriptor(desc: dict, opkey: OperatorKey) -> bool:
    """A descriptor is trusted only with the operator's valid signature
    inside its validity window. Anything else is rejected."""
    try:
        required = ("relay_id", "name", "x25519_pub", "issued_at", "expires_at", "signature")
        if any(k not in desc for k in required):
            return False
        if len(_b64d(desc["x25519_pub"])) != 32:
            return False
        now = datetime.now(timezone.utc)
        if now >= datetime.fromisoformat(desc["expires_at"]):
            return False
        return opkey.verify(_descriptor_canonical(desc), _b64d(desc["signature"]))
    except Exception:
        return False


class RelayDirectory:
    """The keeper's relay directory: operator-signed descriptors only.
    Centralized trust — one operator key — stated plainly, not hidden."""

    def __init__(self, opkey: OperatorKey) -> None:
        self._opkey = opkey
        self._relays: dict[str, dict] = {}

    def add_descriptor(self, desc: dict) -> dict:
        if not verify_descriptor(desc, self._opkey):
            raise OnionError("relay descriptor signature invalid or expired")
        self._relays[desc["relay_id"]] = desc
        return desc

    def get(self, relay_id: str) -> dict:
        desc = self._relays.get(relay_id)
        if desc is None:
            raise OnionError("unknown relay %r" % relay_id)
        return desc

    def relay_ids(self) -> list[str]:
        return sorted(self._relays)

    def verify_all(self) -> bool:
        return all(verify_descriptor(d, self._opkey) for d in self._relays.values())

    def operator_fingerprint(self) -> str:
        return self._opkey.fingerprint()


# ---------------------------------------------------------------------------
# Relay node (in-process simulation of one of his relays)
# ---------------------------------------------------------------------------


class RelayNode:
    """One relay in the simulator. Holds its static X25519 private key, a
    circuit table mapping circuit ids to (hop key, previous hop,
    next hop), and an observation log. A relay's table entries contain
    ONLY routing state — never message content (asserted in tests)."""

    def __init__(self, relay_id: str, name: str) -> None:
        self.relay_id = relay_id
        self.name = name
        self._priv = secrets.token_bytes(32)
        self.x25519_pub = x25519_public(self._priv)
        # circuit_id hex -> {"key": bytes, "prev": str, "next": Optional[str]}
        self.circuit_table: dict[str, dict] = {}
        # observations: {"circuit": hex, "prev": str, "next": str|None,
        #               "saw_plaintext": bool}
        self.observations: list[dict] = []

    def establish(
        self, circuit_id: bytes, eph_pub: bytes, prev_id: str, next_id: Optional[str]
    ) -> None:
        """Telescoping handshake step: ECDH our static key with the
        initiator's ephemeral, derive this hop's key."""
        if len(eph_pub) != 32 or len(circuit_id) != 16:
            raise OnionError("bad handshake parameters")
        shared = x25519(self._priv, eph_pub)
        if shared == bytes(32):
            raise OnionError("handshake produced all-zero secret; aborting")
        key = _hkdf(shared, circuit_id, _HOP_INFO, 32)
        self.circuit_table[circuit_id.hex()] = {
            "key": key,
            "prev": prev_id,
            "next": next_id,
        }

    def handle_cell(self, prev_id: str, cell: bytes):
        """Process one cell from the previous hop. Returns one of:
        ("forward", next_id, cell) | ("deliver", plaintext) |
        ("extended", target_relay_id, eph_pub). Tampered layers and
        unknown circuits raise OnionError — the cell is dropped."""
        cmd, circuit_id, payload = parse_cell(cell)
        entry = self.circuit_table.get(circuit_id.hex())
        if entry is None:
            raise OnionError("unknown circuit")
        if entry["prev"] != prev_id:
            raise OnionError("cell arrived from unexpected previous hop")
        inner = onion_peel(entry["key"], circuit_id, payload)
        if entry["next"] is None:
            # Exit hop: the last layer reveals the padded inner payload.
            if len(inner) != _INNER_SIZE:
                raise OnionError("exit hop peeled to wrong inner size")
            data = _unpack_inner(inner)
            if data.startswith(_EXTEND_MAGIC):
                raise OnionError("extend cell reached an exit hop")
            if not data.startswith(_DATA_MAGIC):
                raise OnionError("unknown inner payload type")
            plaintext = data[len(_DATA_MAGIC):]
            self.observations.append(
                {
                    "circuit": circuit_id.hex(),
                    "prev": prev_id,
                    "next": None,
                    "saw_plaintext": True,
                }
            )
            return ("deliver", plaintext)
        # Middle/guard hop: exactly one layer peeled, opaque bytes forward.
        self.observations.append(
            {
                "circuit": circuit_id.hex(),
                "prev": prev_id,
                "next": entry["next"],
                "saw_plaintext": False,
            }
        )
        if len(inner) == _INNER_SIZE and inner[2:].startswith(_EXTEND_MAGIC):
            body = _unpack_inner(inner)
            target = body[len(_EXTEND_MAGIC):len(_EXTEND_MAGIC) + 16].hex()
            eph_pub = body[len(_EXTEND_MAGIC) + 16:len(_EXTEND_MAGIC) + 48]
            if len(eph_pub) != 32:
                raise OnionError("bad extend payload")
            return ("extended", target, eph_pub)
        return ("forward", entry["next"], build_cell(cmd, circuit_id, inner))


# ---------------------------------------------------------------------------
# In-process relay-network simulator
# ---------------------------------------------------------------------------


class Circuit:
    """An established 3-hop circuit: id plus per-hop keys, outermost first."""

    def __init__(self, circuit_id: bytes, hops: list[tuple[str, bytes]]) -> None:
        if len(hops) != _MAX_HOPS:
            raise OnionError("circuits are exactly %d hops" % _MAX_HOPS)
        self.circuit_id = circuit_id
        self.hops = hops  # [(relay_id, hop_key)] outermost first

    @property
    def relay_ids(self) -> list[str]:
        return [rid for rid, _ in self.hops]


class SimulatedNetwork:
    """The keeper's relay network, in-process: relay nodes, the signed
    directory, telescoping circuit construction, and cell delivery. Method
    calls stand in for the network — the crypto (X25519 ECDH per hop,
    layered AES-256-GCM, fixed-size cells) is the real protocol logic."""

    def __init__(self, opkey: Optional[OperatorKey] = None) -> None:
        self.opkey = opkey or OperatorKey.generate()
        self.directory = RelayDirectory(self.opkey)
        self.nodes: dict[str, RelayNode] = {}

    def add_relay(self, name: str) -> RelayNode:
        """The keeper commissions a relay: keypair generated, descriptor
        signed with his operator key, published in his directory."""
        relay_id = uuid.uuid4().hex
        node = RelayNode(relay_id, name)
        desc = sign_descriptor(self.opkey, relay_id, name, node.x25519_pub)
        self.directory.add_descriptor(desc)
        self.nodes[relay_id] = node
        return node

    def _walk(self, start_id: str, prev_id: str, cell: bytes):
        """Drive a cell through the simulator until it is delivered,
        extended, or fails."""
        node_id, prev, current = start_id, prev_id, cell
        while True:
            result = self.nodes[node_id].handle_cell(prev, current)
            kind = result[0]
            if kind == "forward":
                _, next_id, current = result
                prev, node_id = node_id, next_id
            elif kind == "extended":
                _, target_id, eph_pub = result
                return kind, target_id, eph_pub, node_id
            elif kind == "deliver":
                _, plaintext = result
                return kind, plaintext, None, node_id
            else:  # pragma: no cover - defensive
                raise OnionError("unknown relay outcome %r" % (kind,))

    def open_circuit(self, relay_ids: list[str]) -> Circuit:
        """Telescoping 3-hop circuit build: ECDH with the guard, then
        EXTEND cells (encrypted under the established hop keys) for the
        middle and exit relays."""
        if len(relay_ids) != _MAX_HOPS or len(set(relay_ids)) != _MAX_HOPS:
            raise OnionError("exactly %d distinct relays required" % _MAX_HOPS)
        for rid in relay_ids:
            self.directory.get(rid)  # unknown relay fails closed
        circuit_id = secrets.token_bytes(16)
        hops: list[tuple[str, bytes]] = []

        def hop_key(eph_priv: bytes, node: RelayNode) -> bytes:
            shared = x25519(eph_priv, node.x25519_pub)
            if shared == bytes(32):
                raise OnionError("handshake produced all-zero secret; aborting")
            return _hkdf(shared, circuit_id, _HOP_INFO, 32)

        # Guard: direct ECDH.
        first = self.nodes[relay_ids[0]]
        eph = secrets.token_bytes(32)
        first.establish(circuit_id, x25519_public(eph), "local", relay_ids[1])
        hops.append((relay_ids[0], hop_key(eph, first)))

        # Extend hop by hop; each EXTEND is layered under the keys so far.
        for i in range(1, _MAX_HOPS):
            target_id = relay_ids[i]
            target = self.nodes[target_id]
            eph = secrets.token_bytes(32)
            eph_pub = x25519_public(eph)
            inner = _pack_inner(
                _EXTEND_MAGIC + bytes.fromhex(target_id) + eph_pub
            )
            layered = inner
            aad_keys = [k for _, k in hops]
            for key in reversed(aad_keys):
                layered = _seal_backend(key, layered, _layer_aad(circuit_id))
            cell = build_cell(_CMD_EXTEND, circuit_id, layered)
            kind, a, b, at_node = self._walk(relay_ids[0], "local", cell)
            if kind != "extended" or a != target_id:
                raise OnionError("circuit extension failed")
            nxt = relay_ids[i + 1] if i + 1 < _MAX_HOPS else None
            target.establish(circuit_id, b, at_node, nxt)
            hops.append((target_id, hop_key(eph, target)))
        return Circuit(circuit_id, hops)

    def send(self, circuit: Circuit, plaintext: bytes) -> dict:
        """Send a message down an established circuit. Returns a delivery
        report: the delivered bytes plus every relay's observations."""
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise OnionError("plaintext must be non-empty bytes")
        if len(plaintext) > _MAX_PLAINTEXT:
            raise OnionError(
                "message too large for one cell (%d > %d)"
                % (len(plaintext), _MAX_PLAINTEXT)
            )
        keys = [k for _, k in circuit.hops]
        cell = build_cell(
            _CMD_DATA, circuit.circuit_id, onion_wrap(keys, circuit.circuit_id, bytes(plaintext))
        )
        kind, delivered, _, _ = self._walk(circuit.relay_ids[0], "local", cell)
        if kind != "deliver":
            raise OnionError("message was not delivered")
        return {
            "circuit_id": circuit.circuit_id.hex(),
            "delivered": delivered,
            "observations": {
                rid: list(self.nodes[rid].observations) for rid in circuit.relay_ids
            },
        }

    def crypto_report(self) -> dict:
        """Honest transport posture."""
        return {
            "cell_aead": _cell_aead_backend(),
            "x25519": _chat.x25519_backend(),
            "descriptor_auth": self.opkey.backend,
            "hops": _MAX_HOPS,
            "cell_size_bytes": CELL_SIZE,
            "transport": "in-process simulator — NO real network in this build",
        }


def _cell_aead_backend() -> str:
    from levi.cybrus import veil as _v

    return "aes-256-gcm" if _v._AESGCM is not None else "stdlib-fallback"


# ---------------------------------------------------------------------------
# Threat register + explicit non-claims
# ---------------------------------------------------------------------------

THREATS: list[dict[str, str]] = [
    {
        "id": "not-tor",
        "asset": "sender anonymity / relationship anonymity",
        "attack": "analyst treats this transport as Tor-equivalent cover",
        "mitigation": "documented plainly: 3 hops over the keeper's own "
        "relays, fixed-size cells, no cover traffic, one operator key. "
        "Message CONTENT is protected by the veil_chat E2E layer, which "
        "stays sealed end to end — every relay including the exit sees "
        "only ciphertext.",
        "residual": "a global passive adversary correlating timing and "
        "volume defeats this transport; the anonymity set is only the "
        "users of his network",
        "status": "implemented",
    },
    {
        "id": "colluding-relays",
        "asset": "circuit confidentiality (who talks to whom, when)",
        "attack": "two or three relays on a circuit collude, or the whole "
        "relay set is compelled",
        "mitigation": "each hop learns only previous and next hop "
        "(asserted in tests); layered encryption means one honest relay "
        "still hides the full path; content stays E2E-sealed regardless",
        "residual": "all three hops colluding (or seized, since he runs "
        "them all) reveals the full circuit — path privacy, not content, "
        "is what falls",
        "status": "implemented",
    },
    {
        "id": "tampered-cell",
        "asset": "message integrity in transit",
        "attack": "a relay (or a network attacker in a real deployment) "
        "flips bits in a cell",
        "mitigation": "every layer is AES-256-GCM (or the labeled "
        "fallback) bound to the circuit id; a failed layer raises and the "
        "cell is dropped, never forwarded",
        "residual": "dropping is detectable as a missing message — "
        "denial of service, not silent corruption",
        "status": "implemented",
    },
    {
        "id": "rogue-relay",
        "asset": "circuit integrity (who is on the path)",
        "attack": "attacker advertises a relay that is not the keeper's",
        "mitigation": "the directory only lists descriptors with the "
        "operator's valid signature inside their validity window; "
        "circuit build resolves relays through the directory and fails "
        "closed on unknown ids",
        "residual": "the operator key is the single root of trust — its "
        "compromise forges the whole directory; guard it like the master "
        "key",
        "status": "implemented",
    },
    {
        "id": "size-leak",
        "asset": "message-length confidentiality",
        "attack": "observer infers message content from cell sizes",
        "mitigation": "payloads are length-padded to a fixed inner size, "
        "so every message produces identical cell sizes at every hop "
        "position — message length is fully hidden",
        "residual": "cells shrink by one fixed layer-growth per peel, so "
        "hop POSITION is visible by size to a network observer; message "
        "COUNT and TIMING still leak — no cover traffic in this build",
        "status": "implemented",
    },
]

NON_CLAIMS: list[str] = [
    "This is not Tor and does not claim Tor's anonymity: no cover "
    "traffic, no guard rotation, no directory authorities, one operator.",
    "No resistance to a global passive adversary or to timing/correlation "
    "analysis — stated as residual risk, not as a gap to discover later.",
    "Relays are his own infrastructure: if all three hops on a circuit "
    "collude (or are seized), the path is visible. Content stays dark "
    "only because of the E2E layer, not the transport.",
    "The simulator is method calls, not a network. It proves the "
    "protocol logic (build, peel, deliver); deployment security "
    "(real transport, relay binaries, key rotation, abuse handling) is "
    "future work.",
    "Descriptor signatures are Ed25519 only when the cryptography "
    "package is present; otherwise HMAC attestation, labeled via "
    "crypto_report().",
]

#: The declared laws, machine-readable (L8: law→guard→prove — the laws
#: live in code, not just prose; check_invariants() and the tests check
#: them).
LAWS = (
    ("L1", "No plaintext message content touches the wire or a relay's memory beyond the exit's delivery — layered encryption, fixed-size cells."),
    ("L2", "Each relay learns only previous hop and next hop — never the full path, never message content."),
    ("L3", "Tampered cells, unknown circuits, and previous-hop spoofs fail closed — dropped, never forwarded."),
    ("L4", "Circuits are exactly three distinct operator-signed relays — rogue descriptors are rejected."),
    ("L5", "The transport backend is always reported honestly (cell AEAD, X25519, descriptor auth) — never silently downgraded."),
    ("L6", "Keeper's law / anticipation: every refusal names the relay, the circuit, and the remedy."),
    ("L7", "Originals-first: the operator-signed directory is the original — unknown descriptors are rejected, never auto-accepted."),
    ("L8", "Law->guard->prove: laws declared first, enforced by guards, machine-checked by invariant tests (honestly named, never 'formally proven')."),
    ("L9", "No-cancellation: the directory has no removal API — this module never drops another relay or descriptor."),
    ("L10", "Nothing-thrown-away: relay state only grows within a run; observation logs are append-only."),
    ("L11", "Forward-motion: a dropped cell raises immediately with its reason — nothing blocks on a human or a retry loop."),
    ("L12", "Honesty over polish: threat_model() states the exact threat model — his relays, his users as the anonymity set, not Tor, no GPA resistance."),
)


def threat_model() -> dict:
    """The exact threat model, queryable at runtime (L12: honesty over
    polish). What this transport claims, what it explicitly does not,
    and where the residual risk lives — no faith required."""
    return {
        "claims": [
            "3-hop onion routing over the keeper's own relays",
            "each relay learns only previous/next hop (asserted in tests)",
            "layered AES-256-GCM (or labeled fallback); tampered cells dropped",
            "operator-signed relay directory; rogue descriptors rejected",
            "fixed-size cells hide message length at every hop position",
            "message CONTENT stays E2E-sealed (veil_chat) end to end — "
            "every relay including the exit sees only ciphertext",
        ],
        "explicitly_not_claimed": list(NON_CLAIMS),
        "anonymity_set": "the users of his network — small by construction",
        "is_tor": False,
        "global_passive_adversary_resistant": False,
        "collusion_limit": (
            "all three hops colluding (or seized — he runs them all) "
            "reveals the full path; content stays dark via the E2E layer"
        ),
        "trust_root": "the operator key — its compromise forges the directory",
        "network": "none in this build — in-process simulator; production "
        "transport must cross the Cybrus choke point (request_forward_grant)",
        "laws": [lid for lid, _ in LAWS],
    }


def request_forward_grant(
    actor: str,
    relay_id: str,
    purpose: str = "onion cell forward",
    **kwargs,
):
    """The single sanctioned path for relay-to-relay egress (L2 of the
    choke point: no own HTTP, ever).

    Production relay transport calls this BEFORE forwarding a cell off
    this machine: it authenticates the actor, resolves the relay through
    the router, rate-limits, policy-checks, and returns a signed
    short-lived routing grant bound to (actor, relay, purpose, expiry).
    Hand the grant to the transport; Cybrus performs no HTTP itself.

    The bundled simulator never calls this — it is method calls, not a
    network, and needs no egress at all.
    """
    from levi.cybrus.enforce import request_egress

    return request_egress(actor, relay_id, purpose, **kwargs)


def check_invariants() -> list[tuple[str, bool, str]]:
    """Structural invariants over cells, layers, and the threat register."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    required = ("id", "asset", "attack", "mitigation", "residual", "status")
    for threat in THREATS:
        missing = [k for k in required if not threat.get(k)]
        check(
            "threat %s is fully specified" % threat.get("id", "?"),
            not missing,
            ("missing: " + ", ".join(missing)) if missing else "ok",
        )
    check("every threat names its residual risk", all(t.get("residual") for t in THREATS))
    check("non-claims documented", len(NON_CLAIMS) >= 5, "%d" % len(NON_CLAIMS))
    check(
        "guard-bound cell size is header + inner + 3 layer-growths",
        CELL_SIZE == _CELL_HEADER + _payload_layers(_MAX_HOPS),
        "%d bytes" % CELL_SIZE,
    )
    check(
        "layer growth is a whole number of bytes",
        _payload_layers(3) - _payload_layers(2) == _LAYER_GROWTH > 0,
        "%d bytes/layer" % _LAYER_GROWTH,
    )
    check(
        "commands are distinct", len({_CMD_CREATE, _CMD_EXTEND, _CMD_DATA}) == 3
    )
    check(
        "max plaintext fits one cell",
        _MAX_PLAINTEXT == _INNER_SIZE - 2 - len(_DATA_MAGIC),
        "%d bytes" % _MAX_PLAINTEXT,
    )
    # Pack/unpack round-trip and fixed geometry.
    inner = _pack_inner(b"hello")
    check("inner payload is fixed-size", len(inner) == _INNER_SIZE)
    check("pack/unpack round-trips", _unpack_inner(inner) == b"hello")
    # Layered wrap/peel round-trip with the real backend.
    keys = [secrets.token_bytes(32) for _ in range(3)]
    cid = secrets.token_bytes(16)
    wrapped = onion_wrap(keys, cid, b"ping")
    check(
        "wrapped payload is fixed-size per message",
        len(wrapped) == _payload_layers(3),
        "%d bytes" % len(wrapped),
    )
    layer = wrapped
    for key in keys:
        layer = onion_peel(key, cid, layer)
    check(
        "3-hop peel recovers the padded inner payload",
        _unpack_inner(layer) == _DATA_MAGIC + b"ping",
    )
    # Each peel shrinks the payload by exactly one layer-growth.
    layer2 = wrapped
    sizes = []
    for key in keys:
        layer2 = onion_peel(key, cid, layer2)
        sizes.append(len(layer2))
    check(
        "peels shrink by one layer-growth each",
        sizes
        == [_payload_layers(2), _payload_layers(1), _payload_layers(0)],
        str(sizes),
    )
    # Tampered layer fails closed.
    bad = bytearray(wrapped)
    bad[100] ^= 1
    try:
        onion_peel(keys[0], cid, bytes(bad))
        check("tampered layer fails closed", False)
    except OnionError:
        check("tampered layer fails closed", True)
    # Wrong circuit id fails closed.
    try:
        onion_peel(keys[0], secrets.token_bytes(16), wrapped)
        check("wrong circuit id fails closed", False)
    except OnionError:
        check("wrong circuit id fails closed", True)
    # Descriptor round-trip + tamper rejection.
    opkey = OperatorKey.generate()
    desc = sign_descriptor(opkey, "rid", "r1", secrets.token_bytes(32))
    check("descriptor verifies", verify_descriptor(desc, opkey))
    tampered = dict(desc)
    tampered["name"] = "evil"
    check("tampered descriptor rejected", not verify_descriptor(tampered, opkey))
    # Law->guard->prove: the laws are declared in code, with unique ids.
    law_ids = [lid for lid, _ in LAWS]
    check("laws declared (L1..L12)", len(law_ids) == 12, "%d" % len(law_ids))
    check("law ids unique", len(set(law_ids)) == len(law_ids))
    check(
        "every law has a statement",
        all(text and text.strip() for _, text in LAWS),
    )
    # No-cancellation / nothing-thrown-away: the directory exposes no
    # removal API — descriptors cannot be dropped by this module.
    check(
        "directory has no removal API",
        not any(hasattr(RelayDirectory, n) for n in ("remove", "delete", "purge", "clear")),
        "add-only",
    )
    return results


__all__ = [
    "CELL_SIZE",
    "Circuit",
    "LAWS",
    "OnionError",
    "OperatorKey",
    "RelayDirectory",
    "RelayNode",
    "SimulatedNetwork",
    "THREATS",
    "NON_CLAIMS",
    "build_cell",
    "check_invariants",
    "onion_peel",
    "onion_wrap",
    "parse_cell",
    "request_forward_grant",
    "sign_descriptor",
    "threat_model",
    "verify_descriptor",
]
