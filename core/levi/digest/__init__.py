"""LEVI digest — a local-first mailing-list manager.

REMIX DELTA: BITNET LISTSERV (1981) ran mailing lists on mainframes with
double-opt-in subscription and batched digests — the owner owned the list,
the archive belonged to the members, and attention was never the product.
The giants killed this pattern with engagement-feed inboxes that monetize
attention: lists became audiences, subscribers became inventory, and
moderation became an outsourced content-review farm. This module revives
the list, not the feed:

- :mod:`levi.digest.lists` — list ownership, double-opt-in subscriptions
  (24h token expiry), moderation holds with approve/reject, human-readable
  plain-text digests bucketed by day or ISO week, and a case-insensitive
  local archive search. Stdlib-only, no network, no cloud.

What it ADDS that the giants refuse:
- Owner-controlled lists: the list and its archive live in the owner's
  own ``~/.levi/digest`` store (0700), not on a vendor's servers — no
  platform can demonetize, shadow-ban, or mine it.
- Double-opt-in by construction, with human-moderated holds and a
  rejection log that records *who* rejected and *why* — moderation is
  accountable, not opaque.
- Digests are plain text you read on your schedule: batching as a
  feature, engagement as an anti-feature.

Safety boundaries: digest is mail plumbing, not a mail client — it never
sends mail itself (tokens are handed back to the caller to deliver by
whatever channel they trust). Subscriptions are opt-in only; there is no
bulk-add of addresses. Storage is owner-only (dirs 0700, files 0600).

Research: perpetual-hunt wave-008 (slug ``dead-networks-20260916``).

Run: ``python -m levi.digest --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
    "HOME_DIRNAME",
]

HOME_DIRNAME = "digest"

SHELF = {
    "name": "digest lists",
    "summary": (
        "Local-first mailing-list manager revived from BITNET LISTSERV: "
        "list ownership, double-opt-in subscriptions, moderation holds, "
        "plain-text digests, and a local archive. No network, no cloud, "
        "no engagement feed."
    ),
    "items": [
        "lists: create_list, subscribe/confirm, unsubscribe, post, approve/reject",
        "lists: compile_digest (daily/weekly buckets), archive_search",
        "CLI: python -m levi.digest create|sub|confirm|unsub|post|approve|reject|digest|archive",
    ],
}
