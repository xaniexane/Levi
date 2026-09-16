"""LEVI telegraph — the store-and-forward relay office for offline nodes.

REMIX DELTA: FidoNet (1984) and UUCP (1978) moved mail and jobs between
machines that had no persistent connection, polling on their own schedule.
The giants killed this pattern when always-on internet arrived — and with
it died the only sync model that works when a node is *proudly
disconnected*: LEVI on a laptop, LEVI on a phone with no signal, LEVI on a
farm machine that never sees the cloud. This module revives the envelope,
not the mailer:

- :mod:`levi.telegraph.envelopes` — store-and-forward envelopes. Seal a
  note/file/echo into a node's outbox; another node polls the drop
  directory at its own cadence and carries the envelope home. UUCP-style
  priority grades (0 highest), loop-safe hop trails, expiry honored.
  The wire is the local filesystem (USB, shared folders, plain dirs) —
  the sneakernet, stdlib-only, zero cost.
- :mod:`levi.telegraph.identity` — the telex WRU ritual: every node
  answers "who are you" from its own configured answerback card, and the
  questioner compares the answer against what it registered. Deny-closed:
  an unexpected answerback is quarantined, never trusted. Detection, not
  cryptographic trust — documented as such.
- :mod:`levi.telegraph.directory` — the AppleTalk Chooser, accountless:
  services register human names as ``object:type@zone`` with NBP-style
  conflict detection, browsable by type or zone, persisted as plain JSON.
  No router, no cloud, no account.

What it ADDS that the giants refuse:
- Offline-first node sync with no server anywhere in the loop — the
  cloud sync trade (your data, their servers, their terms) inverted.
- Identity-on-contact as a first-class verb, quarantine by default.
- Accountless zero-config local service directory.

Safety boundaries: envelopes are data, never code — the UUCP ``uux``
remote-execution half is deliberately refused (no arbitrary command
execution from a peer). Directories are owner-only (0700).

Run: ``python -m levi.telegraph --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
    "HOME_DIRNAME",
]

HOME_DIRNAME = "telegraph"

SHELF = {
    "name": "telegraph relay",
    "summary": (
        "Store-and-forward envelopes between offline LEVI nodes over file "
        "drops (FidoNet/UUCP revived), WRU-style node identity with "
        "quarantine-on-mismatch, and an accountless Chooser-style service "
        "directory (AppleTalk NBP revived). No network, no cloud, no accounts."
    ),
    "items": [
        "envelopes: seal/poll/inbox/ack store-and-forward envelopes, grades, hops, expiry",
        "identity: node identity cards, answerback(), handshake() deny-closed",
        "directory: register/lookup/browse object:type@zone names, conflict detection",
        "CLI: python -m levi.telegraph send|poll|inbox|identify|register|names|answerback",
    ],
}
