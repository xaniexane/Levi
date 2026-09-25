"""CLI: python -m levi.trust [laws|demo]

- laws: print the declared laws of the trust module.
- demo: build one earned badge and one explicit-subscription feed item,
  then print the ledger audit, badge verification, and feed audit.
"""

from __future__ import annotations

import json
import sys

from . import __doc__ as MODULE_DOC  # noqa: F401
from .attest import AttestationLedger
from .reach import ExplicitReach, PublisherPost


LAWS = [
    "1. Payment is never valid proof of identity — issue() refuses it.",
    "2. verify() succeeds only for badges present, unrevoked, chain-intact.",
    "3. The receipt chain is tamper-evident — verify_chain() detects edits.",
    "4. Revocation is a public ledger entry, never a quiet delete.",
    "5. A feed contains only explicitly subscribed publishers — rejected at build.",
    "6. Unsubscribing removes reach immediately.",
    "7. audit_insertions() flags any item with a paid/sponsored provenance.",
]


def _demo() -> int:
    ledger = AttestationLedger()
    badge = ledger.issue(
        claim="entity:local-bakery",
        proof="community-vouch:3-of-5",
        issuer="keeper",
    )
    ok, reason = ledger.verify(badge.id)
    feed = ExplicitReach()
    feed.subscribe("pub:bakery", label="The bakery's own posts")
    items = feed.build_feed(
        [PublisherPost(publisher="pub:bakery", title="fresh loaves", body="out at 8am")]
    )
    clean, findings = feed.audit_insertions(items)
    print(
        json.dumps(
            {
                "ledger_audit": ledger.audit(),
                "verify": {"ok": ok, "reason": reason},
                "feed": [
                    {
                        "id": i.id,
                        "publisher": i.publisher,
                        "why_shown": i.why_shown,
                    }
                    for i in items
                ],
                "feed_clean": clean,
                "feed_findings": findings,
            },
            indent=2,
        )
    )
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "demo"
    if cmd == "laws":
        print("\n".join(LAWS))
        return 0
    if cmd == "demo":
        return _demo()
    print("usage: python -m levi.trust [laws|demo]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
