"""LEVI's capability mesh — many machines, one address space, no forgeries.

Studied from: systems-internals survey (Amoeba, capability section).

The mechanism, functionally: every object reference is an *unforgeable
capability token* — a random 128-bit nonce bound to an object id plus a
rights mask by an HMAC keyed with a local secret. Minting and checking
both happen inside the mesh; a token whose HMAC does not verify is
rejected outright, so capabilities cannot be guessed or forged. The mesh
presents many in-process nodes ("machines") as one address space:
``resolve`` finds the object behind a capability wherever it lives.
Blobs are immutable and content-addressed (sha256 of the bytes is the
name). Multi-step transactions stage operations and commit
all-or-nothing: every capability is validated first, then every step
applies; any failure rolls the whole thing back.

Honesty: in-process model — "machines" are Node objects, not hosts.
Capabilities are unforgeable only while the local secret stays local;
that is the stated trust boundary. No network, no real distribution.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/capmesh"

# Rights bits — what a capability permits.
READ = 0b001
WRITE = 0b010
ADMIN = 0b100


class CapError(Exception):
    """Base failure for capability-mesh operations."""


class Capability:
    """An unforgeable token: object id + rights, sealed by HMAC."""

    __slots__ = ("obj_id", "rights", "nonce", "seal")

    def __init__(self, obj_id: str, rights: int, nonce: str, seal: str):
        self.obj_id = obj_id
        self.rights = rights
        self.nonce = nonce
        self.seal = seal

    def token(self) -> str:
        return f"{self.obj_id}:{self.rights}:{self.nonce}:{self.seal}"

    @staticmethod
    def parse(token: str) -> "Capability":
        parts = token.split(":")
        if len(parts) != 4:
            raise CapError("malformed capability token")
        obj_id, rights_s, nonce, seal = parts
        try:
            rights = int(rights_s)
        except ValueError:
            raise CapError("malformed capability rights") from None
        return Capability(obj_id, rights, nonce, seal)

    def allows(self, right: int) -> bool:
        return (self.rights & right) == right


class Node:
    """One 'machine' in the mesh: a local object store."""

    def __init__(self, name: str):
        self.name = name
        self.objects: Dict[str, Any] = {}

    def store(self, obj_id: str, value: Any) -> None:
        self.objects[obj_id] = value

    def fetch(self, obj_id: str) -> Any:
        try:
            return self.objects[obj_id]
        except KeyError:
            raise CapError(f"object {obj_id!r} not on node {self.name!r}") from None

    def drop(self, obj_id: str) -> None:
        self.objects.pop(obj_id, None)


class Mesh:
    """Many nodes presented as one capability-addressed space."""

    def __init__(self, secret: Optional[bytes] = None):
        # The trust boundary: whoever holds this secret mints capabilities.
        self._secret = secret or secrets.token_bytes(32)
        self._nodes: Dict[str, Node] = {}
        self._home: Dict[str, str] = {}  # obj_id -> node name
        self._blobs: Dict[str, bytes] = {}

    # -- nodes ---------------------------------------------------------
    def add_node(self, name: str) -> Node:
        if name in self._nodes:
            raise CapError(f"node {name!r} already in mesh")
        node = Node(name)
        self._nodes[name] = node
        return node

    # -- capabilities --------------------------------------------------
    def _seal(self, obj_id: str, rights: int, nonce: str) -> str:
        msg = f"{obj_id}:{rights}:{nonce}".encode()
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def mint(
        self, node_name: str, value: Any, rights: int = READ | WRITE
    ) -> Capability:
        if node_name not in self._nodes:
            raise CapError(f"unknown node {node_name!r}")
        obj_id = secrets.token_hex(8)
        nonce = secrets.token_hex(16)  # 128-bit
        cap = Capability(obj_id, rights, nonce, self._seal(obj_id, rights, nonce))
        self._nodes[node_name].store(obj_id, value)
        self._home[obj_id] = node_name
        return cap

    def verify(self, token: str) -> Capability:
        """Verify a token; raises CapError on any forgery or tampering."""
        cap = Capability.parse(token)
        expected = self._seal(cap.obj_id, cap.rights, cap.nonce)
        if not hmac.compare_digest(expected, cap.seal):
            raise CapError("forged capability: seal does not verify")
        if cap.obj_id not in self._home:
            raise CapError("capability names an unknown object")
        return cap

    def attenuate(self, token: str, rights: int) -> Capability:
        """Derive a weaker capability from a stronger one."""
        cap = self.verify(token)
        narrowed = cap.rights & rights
        nonce = secrets.token_hex(16)
        return Capability(
            cap.obj_id, narrowed, nonce, self._seal(cap.obj_id, narrowed, nonce)
        )

    # -- one address space ---------------------------------------------
    def resolve(self, token: str, right: int = READ) -> Any:
        cap = self.verify(token)
        if not cap.allows(right):
            raise CapError("capability lacks the required right")
        return self._nodes[self._home[cap.obj_id]].fetch(cap.obj_id)

    def write(self, token: str, value: Any) -> None:
        cap = self.verify(token)
        if not cap.allows(WRITE):
            raise CapError("capability lacks WRITE right")
        self._nodes[self._home[cap.obj_id]].store(cap.obj_id, value)

    # -- immutable content-addressed blobs ------------------------------
    def put_blob(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self._blobs[digest] = data  # same bytes, same name: immutable
        return digest

    def get_blob(self, digest: str) -> bytes:
        try:
            return self._blobs[digest]
        except KeyError:
            raise CapError(f"unknown blob {digest[:12]}…") from None

    # -- atomic transactions --------------------------------------------
    def transact(self, ops: List[Tuple[str, str, Any]]) -> None:
        """All-or-nothing multi-step commit.

        Each op is (action, capability-token, value) where action is
        "write" or "delete". Every capability is verified BEFORE any
        step applies; a failure anywhere aborts with nothing applied.
        """
        verified: List[Tuple[str, Capability, Any]] = []
        for action, token, value in ops:
            if action not in ("write", "delete"):
                raise CapError(f"unknown transaction action {action!r}")
            cap = self.verify(token)
            if action == "write" and not cap.allows(WRITE):
                raise CapError("transaction op lacks WRITE right")
            if action == "delete" and not cap.allows(ADMIN):
                raise CapError("transaction op lacks ADMIN right")
            verified.append((action, cap, value))
        # All verified — now apply. Keep undo info for honest rollback.
        undo: List[Tuple[str, str, Any, bool]] = []
        try:
            for action, cap, value in verified:
                node = self._nodes[self._home[cap.obj_id]]
                existed = cap.obj_id in node.objects
                old = node.objects.get(cap.obj_id)
                if action == "write":
                    node.store(cap.obj_id, value)
                else:
                    node.drop(cap.obj_id)
                undo.append((cap.obj_id, self._home[cap.obj_id], old, existed))
        except Exception:
            for obj_id, node_name, old, existed in reversed(undo):
                node = self._nodes[node_name]
                if existed:
                    node.store(obj_id, old)
                else:
                    node.drop(obj_id)
            raise
