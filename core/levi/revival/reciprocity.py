"""LEVI's reciprocity ledger: earn by serving, spend by consuming.

Studied from: revival-50-more-20260916-0009/report-part2.md (§45).

The studied mechanism meters a peer swarm with an internal currency:
nodes *earn* credit by serving resources to others and *spend* it to
consume. Blocks are content-addressed (the hash of the bytes is the
address — ask for what you want by naming exactly what it is), and the
anti-freeloading rule is accounting, not punishment: you cannot consume
more than the swarm owes you.

LEVI-native remix: ``Swarm`` keeps hash-addressed blocks (``hashlib``
SHA-256 — the address *is* the content fingerprint), a per-node
``ledger`` of credit, and accounted transfers on every serve/fetch.
``seal``/``unseal`` give blocks a keyed wrapper so a block is opaque
without its key.

Honesty: the currency accounting is LOAD-BEARING; the sealing is
ILLUSTRATION-GRADE — a keyed XOR stream cipher built on SHA-256, labeled
exactly as that. It demonstrates "opaque without the key"; it is NOT real
encryption and must never be treated as such. Pricing is linear in block
size; new nodes start at zero and need a ``grant`` (the honest faucet).
Single-process, in-memory, stdlib only, no network.
"""

import hashlib
import os
from collections import defaultdict

ORIGIN = "levi-revival/reciprocity"


class FreeloadError(Exception):
    """A node tried to consume beyond what the swarm owes it."""


def address(data: bytes) -> str:
    """The content address: SHA-256 of the bytes, hex. Name it, get it."""
    return hashlib.sha256(data).hexdigest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def seal(data: bytes, key: bytes) -> bytes:
    """Wrap bytes so they are opaque without the key.

    ILLUSTRATION-GRADE: keyed XOR over a SHA-256 stream — demonstrates the
    shape of "sealed blocks", not real encryption. Do not rely on it.
    """
    if not key:
        raise ValueError("sealing needs a non-empty key")
    nonce = os.urandom(8)
    stream = _keystream(key, nonce, len(data))
    return nonce + bytes(b ^ s for b, s in zip(data, stream, strict=True))


def unseal(blob: bytes, key: bytes) -> bytes:
    """Unwrap what :func:`seal` wrapped. Same honesty applies."""
    nonce, body = blob[:8], blob[8:]
    stream = _keystream(key, nonce, len(body))
    return bytes(b ^ s for b, s in zip(body, stream, strict=True))


class Swarm:
    """A metered swarm: serve to earn, spend to fetch, freeloaders blocked."""

    def __init__(self, price_per_kb=1.0):
        self.price_per_kb = price_per_kb
        self.blocks = {}  # address -> {"sealed": bytes, "size": int, "publisher": node}
        self.ledger = defaultdict(float)  # node -> credit balance
        self.served = defaultdict(int)  # node -> blocks served
        self._grants = defaultdict(float)

    # -- publishing ----------------------------------------------------------
    def publish(self, node, data: bytes, key: bytes) -> str:
        """Seal ``data`` under ``key`` and address it by content hash."""
        sealed = seal(data, key)
        addr = address(data)
        self.blocks[addr] = {"sealed": sealed, "size": len(data), "publisher": node}
        return addr

    # -- the faucet (honest bootstrapping) -----------------------------------
    def grant(self, node, amount):
        """Faucet credit — the only way credit enters the system."""
        if amount < 0:
            raise ValueError("grants cannot be negative")
        self.ledger[node] += amount
        self._grants[node] += amount

    def balance(self, node):
        return self.ledger[node]

    # -- earn by serving, spend by consuming ---------------------------------
    def price(self, addr) -> float:
        return self.blocks[addr]["size"] / 1024 * self.price_per_kb

    def serve(self, server, addr, requester) -> bytes:
        """``server`` serves block ``addr`` to ``requester``.

        The requester pays the block price; the server earns it. If the
        requester cannot cover the price, the transfer is refused —
        accounted reciprocity, not punishment.
        """
        if addr not in self.blocks:
            raise KeyError(f"unknown block {addr[:12]}…")
        cost = self.price(addr)
        if self.ledger[requester] < cost:
            raise FreeloadError(
                f"{requester!r} cannot afford {cost:.3f} "
                f"(balance {self.ledger[requester]:.3f})"
            )
        self.ledger[requester] -= cost
        self.ledger[server] += cost
        self.served[server] += 1
        return self.blocks[addr]["sealed"]

    def fetch(self, node, addr, key: bytes) -> bytes:
        """Fetch a block as a consumer: pay the publisher, unseal with key."""
        publisher = self.blocks[addr]["publisher"]
        sealed = self.serve(publisher, addr, node)
        return unseal(sealed, key)

    def audit(self):
        """The whole ledger, readable — reciprocity you can inspect."""
        return {
            "balances": dict(self.ledger),
            "served": dict(self.served),
            "grants": dict(self._grants),
            "blocks": len(self.blocks),
        }
