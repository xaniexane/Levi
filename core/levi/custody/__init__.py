"""LEVI Custody — the paper chain of custody, revived as local-first primitives.

REMIX DELTA: the giants built custody into invisible vendor databases: SharePoint
workflow history you can only read through their admin console, e-sign logs you
rent back per envelope, approvals that live as notification clicks. The artifact
carries nothing; the vendor carries everything, and you are the product held
hostage by the chain. LEVI inverts it: the chain rides WITH the artifact, readable
and verifiable by anyone holding it, with no server and no vendor in the loop.
What the paper knew: the record and the thing are one traveling object.

Four revived tricks (daily-20260928-custody hunt, 3 ArchiveRecords, all
load-bearing, zero hard-route flags -- stdlib only; browser-hunt-20260929
adds the fourth):

- :mod:`levi.custody.tally` -- Exchequer tally sticks: split-custody agreements.
- :mod:`levi.custody.slip` -- the OF-41 routing slip: the work item carries its chain.
- :mod:`levi.custody.closure` -- wax seals / letterlocking: tamper-EVIDENT closure.
- :mod:`levi.custody.exhibit` -- the evidence bag: sealed claim + metadata +
  attachments with an append-only hash-chained handling log; verdict covers
  custody integrity ONLY (integrity is not truth).

Distinct from :mod:`levi.provenance` (release signing bound to Chauncey's origin
key) and :mod:`levi.commitments` (habit devices): custody is everyday two-party
and transit integrity for any payload, any two parties, no keys required.

LAWS (law-guard-prove; the proof is tests/test_custody.py and
tests/test_custody_exhibit.py):
  1. A tally half never discloses the statement to a stranger -- digests only.
  2. A tally closes only when both halves reunite with matching digests.
  3. Slip blocks are append-only; a slip states what it is NOT (honesty footer).
  4. A closure verdict INTACT means the payload bytes are exactly what was sealed;
     it never claims identity beyond the bound signet.
"""

from __future__ import annotations

SHELF = {
    "name": "custody",
    "summary": (
        "Paper chain-of-custody tricks, revived local-first: split-custody "
        "tallies (tally.py), traveling routing slips (slip.py), tamper-evident "
        "closures (closure.py), sealed evidence exhibits (exhibit.py). "
        "Stdlib only; the chain rides with the artifact."
    ),
    "items": [
        {
            "id": "tally-cut",
            "kind": "function",
            "summary": "Cut a split-custody agreement: two halves, one statement digest.",
            "invoke": "from levi.custody.tally import cut_tally",
        },
        {
            "id": "tally-close",
            "kind": "function",
            "summary": "Reunite both halves; verdict MATCH/MISMATCH/WRONG_PAIR.",
            "invoke": "from levi.custody.tally import close_tally",
        },
        {
            "id": "slip-issue",
            "kind": "function",
            "summary": "Issue a traveling routing slip for a work item with recipients.",
            "invoke": "from levi.custody.slip import issue_slip",
        },
        {
            "id": "slip-sign",
            "kind": "function",
            "summary": "Sign and pass a slip block (initials, date, action code).",
            "invoke": "from levi.custody.slip import sign_slip",
        },
        {
            "id": "closure-seal",
            "kind": "function",
            "summary": "Seal a payload: digest + signet + salt; tamper-evident closure.",
            "invoke": "from levi.custody.closure import seal_payload",
        },
        {
            "id": "closure-inspect",
            "kind": "function",
            "summary": "Inspect a closure against a payload: INTACT/TAMPERED/UNSIGNED.",
            "invoke": "from levi.custody.closure import inspect_closure",
        },
        {
            "id": "exhibit-seal",
            "kind": "function",
            "summary": "Seal a claim + metadata + attachments into an evidence exhibit with a handling log.",
            "invoke": "from levi.custody.exhibit import seal_exhibit",
        },
        {
            "id": "exhibit-log",
            "kind": "function",
            "summary": "Append a chain-of-custody handling entry (append-only, hash-chained).",
            "invoke": "from levi.custody.exhibit import log_handling",
        },
        {
            "id": "exhibit-inspect",
            "kind": "function",
            "summary": "Inspect an exhibit: INTACT/TAMPERED (custody integrity only, never claim truth).",
            "invoke": "from levi.custody.exhibit import inspect_exhibit",
        },
        {
            "id": "exhibit-render",
            "kind": "function",
            "summary": "Render an exhibit as a plain-text evidence card with honesty footer.",
            "invoke": "from levi.custody.exhibit import render_exhibit",
        },
    ],
}

__all__ = ["SHELF"]
