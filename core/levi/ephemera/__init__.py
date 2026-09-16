"""LEVI Ephemera — true-delete ephemeral channels.

REMIX DELTA: Snapchat/Meta sell ephemerality as a feature while keeping
retention backdoors — cloud copies, server logs, "deleted" flags that only
hide. LEVI inverts it: the channel lives entirely on your disk, message
bodies are encrypted at rest with a key only you hold, expiry means the
record file is secure-overwritten (not merely unlinked), and every
deletion emits a hash-chained receipt you can verify. No cloud, no
retention backdoor — because there is nowhere for a backdoor to live.

What it refuses that the giants insist on: server-side storage of your
messages, analytics on your conversations, and the fiction that a
"screenshot notification" stops screenshots (we log access honestly and
say plainly what we cannot prevent).

See docs/EPHEMERA.md for the crypto honesty note.
"""

from __future__ import annotations

SHELF = {
    "name": "ephemera",
    "summary": (
        "True-delete ephemeral channels: local encrypted-at-rest message "
        "store, per-channel TTL, hash-chained deletion receipts, secure "
        "overwrite on expiry, and honest access logging."
    ),
    "items": [
        {
            "id": "channel-create",
            "kind": "command",
            "summary": "Create a channel with a TTL and a passphrase.",
            "invoke": "python -m levi.ephemera create NAME --ttl SECONDS",
        },
        {
            "id": "channel-post",
            "kind": "command",
            "summary": "Post an encrypted message (optionally forwarding-discouraged).",
            "invoke": "python -m levi.ephemera post CHANNEL --author NAME --body TEXT",
        },
        {
            "id": "channel-read",
            "kind": "command",
            "summary": "Read (decrypt) a message; the read is access-logged.",
            "invoke": "python -m levi.ephemera read CHANNEL MSG_ID",
        },
        {
            "id": "channel-sweep",
            "kind": "command",
            "summary": "Secure-overwrite + delete expired messages, emit receipts.",
            "invoke": "python -m levi.ephemera sweep [CHANNEL]",
        },
        {
            "id": "receipts-verify",
            "kind": "command",
            "summary": "Verify the hash chain of deletion receipts.",
            "invoke": "python -m levi.ephemera receipts CHANNEL",
        },
        {
            "id": "access-log",
            "kind": "command",
            "summary": "Inspect who read what and when.",
            "invoke": "python -m levi.ephemera access CHANNEL",
        },
    ],
}
