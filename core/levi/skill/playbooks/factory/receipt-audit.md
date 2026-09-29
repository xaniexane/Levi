---
skill_id: factory.receipt_audit
name: Receipt Audit
description: Audits a factory receipt for completeness against the factory receipt format.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, receipts, audit, integrity]
version: "1.0.0"
---

# Receipt Audit

Audits one factory receipt for completeness against the receipt format
(`core/levi/factory/genesis/receipt_format.md`). Advisory only.

## How to audit

- Required sections: Spec ID, Kind, Minted, Builder glyph, Final name
  status, Spec, Build, Proof, Registry, Gated.
- The proof section must name the tests and the count (e.g. 3/3), and the
  commit hash must exist in `git log`.
- The glyph trailer must verify: `git log -1 --format=%B | grep "Agent-Glyph:"`.

## Laws

1. Never mark a receipt complete when a required section is missing.
2. Never invent test counts — read them from the test run.
3. Never fabricate a commit hash — check `git log`.
4. Incomplete receipts get named, not fixed silently.

## Limits

- Never edits or rewrites a receipt to pass the audit.
- Never commits anything; the audit reports, the builder fixes.

## Notes

- Pairs with the Receipt Clerk agent (receiptclerk): the agent finds
  missing receipts, this skill audits the ones that exist.
