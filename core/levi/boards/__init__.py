"""LEVI boards — charter-governed local message areas (the community board).

REMIX DELTA: BBS message areas (1980s-90s) ran on written charters,
named moderators, and offline QWK packets a caller carried home to read
at their own desk; FidoNet echomail held whole networks of nodes to one
shared charter per echo; Free-Nets gave entire cities free local boards.
The giants killed this pattern twice: first with engagement feeds where
no one writes the rules and no human moderator signs their work, then
with vanishing subscription libraries where your reading history is
rented, not yours. This module revives the board, not the modem:

- :mod:`levi.boards.areas` — charter-required areas. No charter, no
  area: the charter is a required argument, hashed, and shipped inside
  every portable packet. Human moderation with recorded reasons:
  every approve/reject names the moderator and timestamps the act, and
  rejections require a written reason. Per-reader seen-tracking that
  lives on the reader's own disk (idempotent: a second read returns
  nothing new). Portable offline packets — one JSON file per area,
  explicitly NOT QWK-compatible (clean-room format), carrying the
  area, its charter hash, and its approved messages.

What it ADDS that the giants refuse:
- Charters as code-enforced prerequisites, not vibes: an area cannot
  exist without a written charter.
- Moderation is accountable and inspectable — recorded reasons and
  moderator names in plain JSON, no shadow decisions.
- Offline-first portability: an area's messages travel on foot (USB,
  shared folders, plain dirs) with integrity via charter hash.
- Per-reader read state with no accounts, no ads, no engagement
  scoring, no cloud anywhere in the loop.

Research lineage: perpetual-hunt wave-008 (research slug
``dead-networks-20260916``).

Safety boundaries: everything is plain JSON under the area dir, owned
by the local user (dirs 0700, files 0600). Imported packets are data,
never code — nothing is executed, and unknown packet formats are
refused, never guessed.

Run: ``python -m levi.boards --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
    "HOME_DIRNAME",
]

HOME_DIRNAME = "boards"

SHELF = {
    "name": "boards",
    "summary": (
        "Charter-governed local message areas (BBS/FidoNet echomail/Free-Net "
        "community boards revived): charter-required areas, human moderation "
        "with recorded reasons, per-reader seen-tracking, and portable "
        "offline packets. No accounts, no ads, no cloud."
    ),
    "items": [
        "areas: create_area/charter/post/queue/approve/reject/read",
        "packets: export_packet/import_packet — clean-room offline format, not QWK-compatible",
        "seen-tracking: per-reader unseen message lists, idempotent",
        "CLI: python -m levi.boards create|charter|post|queue|approve|reject|read|export|import",
    ],
}
