---
skill_id: cyber_performing_entitlement_review_with_sailpoint_iiq
name: Entitlement Review with SailPoint IIQ
description: Run identity access certifications to validate entitlements and revoke excess access.
risk: info
permissions: []
requires_confirmation: false
tags: [iam, governance, audit]
version: 1.0.0
---
# Entitlement Review with SailPoint IIQ

## Purpose

Access accumulates: roles change, projects end, and entitlements quietly
linger. Periodic access certification — reviewers confirming each identity
still needs its access — is the corrective control. This playbook runs a
defensible entitlement review campaign in SailPoint IdentityIQ from scoping
to revocation.

## When to use

- Quarterly or annual access-recertification campaigns.
- After reorganizations, mergers, or mass role changes.
- Before audits (SOX, ISO 27001, SOC 2) that test least-privilege.
- When dormant privileged accounts or orphaned identities are suspected.

## Prerequisites

- SailPoint IIQ access with certification-administrator rights and
  authoritative identity/application data already aggregated.
- Defined reviewer model: managers certify their reports' access,
  application owners certify privileged or sensitive entitlements.
- Remediation workflow owners: who revokes access and on what timeline
  once a reviewer rejects an item.

## Procedure

1. Scope the campaign: populations (all identities, privileged users,
   contractors), applications, and entitlement types; exclude service
   accounts from human review and handle them separately.
2. Validate identity data first: reconcile HR joiners/movers/leavers
   against IIQ identities so reviewers are not certifying stale
   populations.
3. Build the certification: choose manager or application-owner
   certification type, set the campaign duration, and configure
   auto-revocation or manual fulfillment for rejected items.
4. Brief reviewers: what "certify" means, how to spot toxic
   combinations (e.g. requester-plus-approver in financial systems),
   and that rubber-stamping has audit consequences.
5. Monitor campaign health: chase non-responders, escalate per policy,
   and track decision distributions — 100% approval rates indicate
   reviewers are not engaging.
6. Process decisions: route rejections to fulfillment, verify
   deprovisioning completed in the target systems, and document items
   kept with business justification.
7. Report results: revocation counts, non-responder handling,
   exceptions granted with expiry, and coverage of privileged access.
8. Feed lessons back: adjust role models for entitlements that are
   always revoked (they should never have been granted) and always
   approved (candidates for automated provisioning).

## Expected outputs

- A completed certification campaign with signed reviewer decisions.
- Verified deprovisioning of revoked entitlements in target systems.
- An exception register with business justification and review dates.
- Audit evidence: campaign scope, reviewer attestations, remediation
  records.

## Pitfalls

- Certifying stale data: a review of wrong identities is worse than no
  review because it creates false assurance.
- Rubber-stamping: address it with spot audits, not just reminders.
- Letting revocations sit in a queue: access removed in IIQ but still
  active in the target system is a finding, not a fix.
- Including service and break-glass accounts in human review instead of
  owner-based controls.

## References

- NIST SP 800-53, Access Control family (AC-2, AC-5, AC-6)
- ISO/IEC 27001:2022, Annex A 5.15–5.18 (access control)
- SailPoint IdentityIQ certification documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
