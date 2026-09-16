"""LEVI capproto — the capability-gated service protocol.

REMIX DELTA: Twitter and Reddit proved the giant pattern — rent out API
access, get developers hooked, then reprice or revoke the API at will
(Discord/Reddit API betrayals). MCP won by being a protocol, but it is
still a vendor-shaped artifact you *connect to*. capproto inverts both:
it is a stdlib-native, vendorless wire protocol where every call is gated
by a bearer capability token issued by the *service owner* — not by a
platform. Nobody can reprice what nobody owns; the revocation right stays
with the local issuer, and every mint/attenuation/revocation is recorded
in an owner-only audit ledger on this machine.

Built on top of (not duplicating) :mod:`levi.revival.telescript` token
primitives. What capproto ADDS, that no giant will ship because it breaks
their toll booths:

- Macaroon-style ATTENUATION: hold a broad token, mint a strictly
  narrower one (subset of action patterns, earlier-or-equal expiry).
  Tokens can be delegated downward without ever widening them — the
  thing that makes API resale/repricing impossible by construction.
- A documented wire spec (``capproto/1``, newline-delimited JSON) with
  deny-closed service verbs, usable over AF_UNIX sockets or loopback TCP.
- A persistent revocation list + mint/attenuation ledger under
  ``~/.levi/capproto`` (owner-only), so a revoked token stays revoked
  across restarts.

Stdlib-only. Local-first. No network beyond this machine.
"""

from __future__ import annotations

__all__ = ["SHELF"]

SHELF = {
    "name": "capability protocol",
    "summary": (
        "Vendorless capability-gated service protocol (capproto/1): token "
        "issuance/attenuation/verification, deny-closed service verbs, and "
        "local socket transport — an API nobody can reprice."
    ),
    "items": [
        "tokens: attenuate / decode / MintLedger (macaroon-style narrowing over telescript)",
        "protocol: capproto/1 wire spec, message validation, ServiceSpec dispatch gating",
        "transport: AF_UNIX + loopback-TCP server/client",
        "demo: kvnote demo service + client; CLI issue/attenuate/verify/serve/call/demo",
    ],
}
