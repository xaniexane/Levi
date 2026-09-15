---
skill_id: cyber_performing_privileged_account_access_review
name: Privileged Account Access Review
description: Recertify privileged accounts and entitlements on a regular cycle to enforce least privilege and remove stale access.
risk: info
permissions: []
requires_confirmation: false
tags: [pam, access-review, governance]
version: 1.0.0
---

## Purpose
- Ensure every privileged account and entitlement is still needed, still owned, and still appropriate.
- Catch orphaned, shared, and over-privileged accounts that accumulate between reviews.
- Produce audit-ready evidence that access recertification actually happens.

## When to use
- On a regular cycle, typically quarterly for the most sensitive privileged access.
- After reorganizations, outsourcing changes, or major system migrations.
- When auditors or regulators ask for recertification evidence.
- After incidents involving privileged account misuse.

## Prerequisites
- A complete inventory of privileged accounts: admins, service accounts, break-glass, and cloud privileged roles.
- Identified reviewers with the business context to judge necessity, typically system and data owners.
- Access review tooling or a structured process with tracking, reminders, and escalation.
- Defined outcomes: certify, modify, or revoke, with SLAs for actioning revocations.

## Procedure
1. Freeze the inventory snapshot and confirm it covers all privileged account types and platforms.
2. Assign each account and entitlement to a reviewer who understands the business need.
3. Provide reviewers with context: last logon, usage patterns, and what the access grants.
4. Collect decisions: certify as still needed, modify scope, or revoke.
5. Challenge rubber-stamping: sample reviewer decisions and follow up on anything certified without scrutiny.
6. Execute revocations and modifications within the defined SLA and verify they took effect.
7. Investigate anomalies found during review: orphaned accounts, unknown owners, and dormant-but-privileged access.
8. Document the review cycle: scope, participants, decisions, and completion rates.
9. Report metrics to leadership: revocation counts, overdue reviews, and repeat findings.
10. Feed lessons back into provisioning: fix the joiner-mover-leaver gaps that created the stale access.

## Expected outputs
- A completed review with certify, modify, or revoke decisions for every privileged account.
- Executed revocations with verification.
- Audit evidence and metrics for the review cycle.
- A joiner-mover-leaver gap analysis explaining how the stale access accumulated.
- Trend metrics showing the privileged footprint shrinking over successive cycles.

## Pitfalls
- Letting managers bulk-certify without looking; sampling and accountability prevent this.
- Reviewing entitlements but ignoring the accounts themselves, missing orphaned and shared credentials.
- Recording revoke decisions that never get executed; track through to verified removal.

## References
- NIST SP 800-63 digital identity guidance on privileged authenticators
- NIST SP 800-53 access control family (AC-2, AC-6)
- ISO/IEC 27001 access control requirements
- CIS Controls on account management
- Vendor PAM documentation for the platforms in use
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
