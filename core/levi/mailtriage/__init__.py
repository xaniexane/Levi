"""LEVI mailtriage — sovereign mail triage over a LOCAL mail store.

REMIX DELTA: Google built Inbox — snooze, bundles, smart reply — then
killed it and strip-mined the features into Gmail, where the price of
admission is being scanned. The giant pattern: a beloved capability is
held hostage to surveillance. The remix inverts the bargain: the full
triage surface (snooze, bundles, rule-based smart replies) runs against
the user's OWN local maildir/mbox, read-only, with zero network and zero
accounts. No scanning, because there is nobody to sell the scan to.

What it ADDS that the giants refuse:
- Snooze with explicit, user-visible rules (until a time / until a reply
  arrives), stored in an owner-only local ledger — the snooze state is
  *yours*, inspectable as JSON, not a black box.
- Bundles as readable, editable local rules (receipts, newsletters,
  people, notifications) — not engagement-tuned classifiers.
- Smart replies as TEMPLATE-BASED drafts the user explicitly approves.
  Rule-based drafting, no model, and honest about it: every draft is
  labeled "template draft — not sent" and nothing is ever sent without
  an explicit command.

Hard safety lines: the store reader is READ-ONLY against the user's real
mail; triage state (snooze/drafts) lives separately under
``~/.levi/mailtriage``. Nothing is modified, moved, or deleted in the
user's mail without an explicit command. No network, no accounts.
"""

from __future__ import annotations

__all__ = ["SHELF"]

SHELF = {
    "name": "mail triage",
    "summary": (
        "Sovereign mail triage (Inbox's best ideas, minus the surveillance): "
        "snooze, rule-based bundles, and template smart-reply drafts over a "
        "local read-only maildir/mbox. No network, no accounts."
    ),
    "items": [
        "store: read-only maildir/mbox reader (stdlib mailbox+email)",
        "triage: bundles (receipts/newsletters/people/notifications), snooze ledger (until time/until reply)",
        "replies: template-based smart-reply drafts, user-approves, never auto-sent",
        "CLI: inbox/bundles/snooze/unsnooze/draft/approve over the local store",
    ],
}
