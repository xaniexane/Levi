---
skill_id: factory.deposit_tracker
name: Deposit Tracker
description: Records and tracks expected deposits; projection vs confirmed is never conflated.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, deposits, ledger, tracking]
version: "1.0.0"
---

# Deposit Tracker

Tracks expected deposits against the DDD deposits ledger. Projections and
confirmed receipts are never conflated — the ledger says what it says.

## How to read the ledger

- Source: `~/workspace/ddd/launch/ledger/*.jsonl`.
- Entries carry `kind: expected` or `kind: received`.
- Report the two counts side by side with the gap.

## Laws

1. Never confirm a deposit — only the ledger's `received` entries count.
2. Expected and received are never summed into a single number.
3. No revenue claims: a projection is a projection.
4. Missing ledger directory means zero, said plainly.

## Limits

- Never writes ledger entries; never edits the ledger.
- Never claims a deposit happened; never spends or moves money.

## Notes

- Pairs with the Ledger Warden agent (ledgerwarden): the agent wards,
  this skill tracks for a human reading.
