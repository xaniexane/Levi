---
skill_id: cyber_testing_for_business_logic_vulnerabilities
name: Testing for Business Logic Vulnerabilities
description: Authorized testing of application workflows for logic abuse: race conditions, quantity tampering, and flow bypass.
risk: low
permissions: []
requires_confirmation: false
tags: [web, business-logic, testing]
version: 1.0.0
---
## Purpose
Business logic flaws abuse legitimate functionality in unintended ways: negative quantities, race conditions on limited inventory, coupon stacking, or skipped verification steps. Scanners cannot find these. This playbook covers authorized, manual testing of your own applications' workflows, designed to be safe for staging and carefully bounded in production.

## When to use
- Security review of transactional features (checkout, transfers, booking, rewards).
- After adding promotions, credits, or multi-step verification flows.
- Investigating fraud patterns that suggest logic abuse.
- Threat modeling new business workflows.

## Prerequisites
- Written authorization with explicit bounds (test accounts, transaction limits, staging preferred).
- Deep understanding of the intended workflow: steps, limits, and invariants.
- Test accounts with controlled balances and the ability to reset state.
- Proxy tooling and, for race conditions, request-replay automation.

## Procedure
1. Map the workflow end to end: steps, state transitions, limits, and trust boundaries.
2. List the invariants that must hold (e.g. balance never negative, one coupon per order, verification before payout).
3. Test parameter tampering: negative/zero quantities, oversized values, currency or price fields.
4. Test race conditions: submit concurrent requests for limited resources and check for double-spend.
5. Test flow bypass: skip, reorder, or replay steps (especially verification and payment confirmation).
6. Test abuse of legitimate features: coupon stacking, referral farming, trial resets.
7. Quantify impact in business terms (financial exposure per abuse) to prioritize fixes.
8. Verify fixes preserve the invariant under retest, including the race-condition retest.
9. Involve product owners in defining invariants; security cannot guess business rules.
10. Document the abuse scenarios as misuse cases for future feature design reviews.
11. Re-test invariants after every related feature change, not just after the initial fix.

## Expected outputs
- Workflow maps with invariants and abuse cases per step.
- Findings with business-impact quantification.
- Retest evidence confirming invariants hold.
- Business invariant catalog with product-owner sign-off.
- Misuse-case library for design reviews.
- Invariant regression test results per release.

## Pitfalls
- Testing logic flaws in production with real money or inventory is dangerous; use staging or strict limits.
- Race conditions are timing-sensitive; a single clean test does not prove the fix.
- Developers often fix the reported parameter while the invariant remains unenforced elsewhere.
- Fraud and security teams must share findings; logic abuse sits on their boundary.
- Fixes that add only client-side checks are not fixes; verify server-side enforcement.
- Invariants documented nowhere get violated by the next feature; write them down.
- Fraud teams and security teams must share logic-abuse findings; they see different halves.
- Currency and rounding logic deserve dedicated review; small errors compound at scale.

## References
- OWASP Web Security Testing Guide: business logic testing.
- OWASP API Security Top 10: unrestricted business flows.
- PortSwigger Web Security Academy: business logic vulnerabilities.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
