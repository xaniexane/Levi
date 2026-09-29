---
skill_id: red_email_collection_test
name: Email Collection Test
description: Test mailbox collection rules and exports to validate email-security monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, email, exfiltration]
version: 1.0.0
team: red
tests_blue: cyber_analyzing_outlook_pst_for_email_forensics
---
# Email Collection Test

## Purpose

Attackers collect email with inbox rules (forwarding, auto-BCC) and bulk exports. This
test creates canary collection rules and validates whether mailbox-auditing and email-
security controls detect them.

## When to use

- During collection phases in M365/Google Workspace.
- To validate inbox-rule alerting and mailbox-audit logging.
- After phishing tests, as the post-compromise email-persistence check.

## Prerequisites

- Authorization for the test mailboxes; canary rules only.
- Mail-admin coordination for audit-log verification.

## Procedure

1. Create canary inbox rules: forward-to-external (canary address), move-to-RSS, mark-read-
   and-move.
2. Perform a canary mailbox export (eDiscovery-style, authorized) and record the audit
   trail.
3. Monitor detection: did rule-creation alert? Did the export generate the expected audit
   events?
4. Test the hidden-rule variant (rule with no client-visible UI change) where applicable.
5. Remove all canary rules; verify via audit log and rule enumeration.
6. Deliver the email-collection monitoring assessment.

## Expected outputs

- Per-rule detection results.
- Export audit-trail assessment.
- Rule-removal verification.

## Pitfalls

- Forwarding to real external addresses — canary addresses only.
- Exporting real mailboxes beyond the canary scope — scope strictly.
- Leaving rules behind — enumerate and verify removal.

## References

- MITRE ATT&CK: Email Collection (T1114).

## Blue-team control under test

This playbook validates their mailbox auditing and inbox-rule alerting are under test —
silent forwarding rules are the business-email-compromise gap. Paired blue-team
counterpart: `cyber_analyzing_outlook_pst_for_email_forensics`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
