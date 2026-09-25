"""Void Box Messenger — the STANDALONE messenger surface.

Messenger vs the Void Box platform, like Messenger vs Facebook: this is
the chat surface only. It builds on the same crypto the platform
uses (``veil_chat`` for 1:1, ``rooms`` for groups, the ``relay`` for
transport), but it is its own deliverable — own CLI
(``python -m levi.voidbox.messenger``), own entry points
(:class:`levi.voidbox.messenger.app.Messenger`), no platform imports.

What it does
------------
- 1:1 conversations through ``levi.cybrus.veil_chat`` (X25519 handshake,
  per-message ratchet, sealed envelopes).
- Group conversations through ``levi.voidbox.rooms`` (per-room keys,
  re-key on membership change, replay protection).
- Transport through ``levi.voidbox.relay``: sealed envelopes travel as
  opaque packets addressed to keeper ids; the messenger POSTs and
  POLLs, then dispatches by packet kind and room id. Group messages
  are fanned out to each active member's own mailbox (per-member acks
  must never delete another member's copy). The relay never sees
  plaintext — structurally, not by promise.

How group state reaches members: a room lives in each keeper's own
``RoomStore``. When the admin adds/removes a member (which re-keys the
room), the admin's messenger exports that member's room state and ships
it to them sealed INSIDE the 1:1 E2E channel — epoch keys cross the
wire only under the recipient's DM session key, never in the clear.
The receiving messenger re-wraps them under its own master-derived
keys. This is the keeper model: the messenger seals/opens only with
the keeper's own keys, and it never opens plaintext that isn't
addressed to the keeper or to a room the keeper belongs to.

SI side: every public entry point calls
``levi.plaiground.gate.require_adult()`` FIRST — adult-only, default
OFF, minors hard-locked out.

LAWS (declared here, enforced by guards, machine-checked by
``Messenger.verify_laws()`` and the invariant tests — honestly named,
never "formally proven")
---------------------------------------------------------------
- M1 — Separate surface: own CLI, own entry points, no platform
  imports. The messenger consumes only the crypto primitives
  (``veil_chat``, ``rooms``), the ``relay`` transport, and the
  plaiground gate.
- M2 — 1:1 via veil_chat: DMs are sealed/opened only by the keeper's
  own ``VeilChat``; the messenger never re-keys peer material, never
  touches another keeper's store.
- M3 — Groups via rooms: group crypto lives in ``RoomStore``; the
  messenger seals/opens only with the keeper's own membership and its
  own key copies.
- M4 — Transport is the relay: envelopes travel as opaque packets
  addressed to keeper ids; the messenger POSTs and POLLs and
  dispatches by packet kind and room id. It invents no transport of
  its own.
- M5 — Ciphertext-only carrier: room-sync payloads travel sealed inside
  the 1:1 E2E channel; epoch keys never cross the wire in the clear.
- M6 — No plaintext beyond the keeper: the messenger opens only
  envelopes addressed to the keeper or to a room the keeper is a
  member of, and only with the keeper's own keys.
- M7 — Adult gate first: every public entry point calls
  ``require_adult()`` before any other work — default OFF, minors
  hard-locked out; every refusal names its remedy.
- M8 — Honest addressing: the relay routes on plaintext ids, so WHO
  talks to WHOM is visible to the relay operator. The messenger names
  this; it does not hide it.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

#: The declared laws, machine-readable (law→guard→prove — the laws live
#: in code, not just prose; verify_laws() and the invariant tests check
#: them at runtime).
LAWS = (
    ("M1", "Separate surface: own CLI, own entry points, no platform imports — only the crypto primitives (veil_chat, rooms), the relay transport, and the plaiground gate."),
    ("M2", "1:1 via veil_chat: DMs are sealed/opened only by the keeper's own VeilChat; the messenger never re-keys peer material, never touches another keeper's store."),
    ("M3", "Groups via rooms: group crypto lives in RoomStore; the messenger seals/opens only with the keeper's own membership and its own key copies."),
    ("M4", "Transport is the relay: envelopes travel as opaque packets addressed to keeper ids; the messenger POSTs and POLLs and dispatches by packet kind and room id — no home-grown transport."),
    ("M5", "Ciphertext-only carrier: room-sync payloads travel sealed inside the 1:1 E2E channel; epoch keys never cross the wire in the clear."),
    ("M6", "No plaintext beyond the keeper: the messenger opens only envelopes addressed to the keeper or to a room the keeper belongs to, and only with the keeper's own keys."),
    ("M7", "Adult gate first: every public entry point calls require_adult() before any other work — default OFF, minors hard-locked out; every refusal names its remedy."),
    ("M8", "Honest addressing: the relay routes on plaintext ids, so WHO talks to WHOM is visible to the relay operator — named, not hidden."),
)

NON_CLAIMS: list[str] = [
    "No push notifications, no contact discovery, no read receipts, no "
    "typing indicators — delivery is poll-based; the messenger never "
    "learns a peer's network location.",
    "The relay routes on plaintext recipient ids: who talks to "
    "whom, how often, and when is visible to whoever runs the relay — "
    "relationship mapping, not content. Group messages are fanned out "
    "per member, so the relay also sees group size. Use pseudonymous "
    "keeper ids if that matters.",
    "No sender authentication on the transport in this build — "
    "reachability is the access control (relay L8). Envelope-level "
    "authenticity still holds: forged DM envelopes fail the veil_chat "
    "AAD checks, forged group envelopes fail the room AAD checks.",
    "No multi-device: one keeper id is one device store in this build. "
    "A second device is a second keeper id.",
    "First contact needs an out-of-band public-key exchange: a "
    "handshake offer from an unregistered peer is parked, not answered "
    "— the messenger never TOFUs a stranger's identity key.",
    "One process per handshake: veil_chat keeps the handshake's "
    "ephemeral key in memory only, so the offer and the peer's answer "
    "must be handled by a single Messenger lifetime — start_dm "
    "posts the offer and, with wait_seconds > 0 (dm-start --wait), "
    "stays to finish it. A restarted process re-runs start_dm for a "
    "fresh offer; the stale answer is rejected harmlessly.",
    "read_dm/read_group hold the other kind's messages in a MEMORY-"
    "only buffer for the next matching read — poll_inbox always "
    "returns everything swept. A process restart between a read_dm "
    "and the matching read_group can strand a held message (it was "
    "already acked); long-lived processes should prefer poll_inbox.",
    "Group rooms have no forward secrecy against keeper compromise "
    "(rooms NON_CLAIMS); DMs ratchet per veil_chat.",
]

from levi.voidbox.messenger.app import Messenger, MessengerError  # noqa: E402
from levi.voidbox.messenger.client import MessengerTransport  # noqa: E402

__all__ = [
    "LAWS",
    "NON_CLAIMS",
    "Messenger",
    "MessengerError",
    "MessengerTransport",
]
