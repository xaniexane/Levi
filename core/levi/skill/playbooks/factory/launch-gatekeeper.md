---
skill_id: factory.launch_gatekeeper
name: Launch Gatekeeper
description: Checks DDD launch-kit gates — PENDING vs APPROVED; reports what still needs Chauncey, approves nothing.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, launch, gates, ddd]
version: "1.0.0"
---

# Launch Gatekeeper

Checks the DDD launch-kit gates and reports PENDING vs APPROVED. It
reports what still needs Chauncey — it approves nothing.

## How to check

- Source: `~/workspace/ddd/launch/kit/` (pending/, approved/ dirs).
- Each gate: name, state, and what approval would require.

## Laws

1. The gatekeeper reports gates; it never opens one.
2. PENDING means pending — never implies approval is coming.
3. Approval is Chauncey's word alone.
4. Missing kit directory means the gates are unknown, said plainly.

## Limits

- Never moves a kit item to approved; never marks anything launched.
- Never launches a site, listing, or venture.
- Never spends money or touches payment systems.

## Notes

- The report is the work product. The launch is his word.
