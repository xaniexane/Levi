---
skill_id: factory.budget_ledger_post
name: Budget Ledger Post
description: Posts an income record to the budget ledger with the required source field; projections labeled, never conflated.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, budget, ledger, income]
version: "1.0.0"
---

# Budget Ledger Post

Posts an income record to the budget ledger. Every record carries the
required `source` field; projections are labeled and never conflated
with received income.

## How to post

- Fields: amount, source (required), kind (expected|received), date,
  note.
- Expected income and received income are separate record kinds — never
  summed in one line.

## Laws

1. The `source` field is required — a record without a source is rejected.
2. Expected vs received are never conflated; never summed.
3. Never claim a projection as income — projections are projections.
4. The ledger is append-only: corrections are new records, never edits.

## Limits

- Never edits or deletes an existing ledger record.
- Never moves money; the ledger records, it never transacts.
- Never invents a source — the source is what Chauncey said it is.

## Notes

- The launch-kit gate check (pending vs approved) is separate — see the
  launch-gatekeeper skill.
