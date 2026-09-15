---
skill_id: cyber_performing_access_recertification_with_saviynt
name: Performing Access Recertification with Saviynt
description: Run periodic access recertification campaigns in Saviynt for least-privilege enforcement.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, access-review, saviynt]
version: 1.0.0
---

## Purpose
This playbook runs access recertification campaigns in Saviynt: reviewers attest whether each person's entitlements are still needed, unjustified access gets revoked, and the whole cycle is evidenced for audit.

## When to use
- Satisfying periodic access-review requirements (SOX, PCI, ISO 27001).
- Cleaning up entitlement sprawl after mergers, reorganizations, or rapid growth.
- Standing up identity governance on the Saviynt platform.

## Prerequisites
- Saviynt connected to authoritative sources (HR) and target applications with entitlement catalogs.
- Defined reviewer model: managers for user access, application owners for privileged/entitlement-level reviews.
- Campaign scope, cadence, and escalation rules agreed with compliance.

## Procedure
1. **Define the campaign scope.** Choose applications, entitlement types, and populations; start with privileged access and critical apps, then expand.
2. **Prepare identity data.** Reconcile HR joiner/mover/leaver data so reviewers see accurate job context; stale HR data produces rubber-stamp reviews.
3. **Configure reviewers and workflows.** Assign manager vs. app-owner review tasks, set durations, and define escalation for non-responsive reviewers.
4. **Launch with communication.** Notify reviewers what is expected, how to decide, and the deadline; provide entitlement descriptions in business language, not cryptic codes.
5. **Monitor and escalate.** Track completion daily; escalate overdue reviews per policy; never auto-approve by default on timeout.
6. **Execute revocations.** Process denied entitlements promptly through automated deprovisioning; verify removal in target systems.
7. **Report and improve.** Deliver campaign metrics (completion rate, revocation rate, overdue reviews) to compliance; use high-revocation areas to tighten birthright provisioning.

8. **Integrate leavers aggressively.** Same-day deprovisioning for terminated employees is the highest-value recertification outcome; measure it separately.
9. **Use campaign data strategically.** Entitlements denied repeatedly across campaigns indicate broken provisioning logic — fix the birthright rules, not just the symptoms.

## Expected outputs
- Completed campaign with reviewer attestations and audit trail.
- Revocation records with verification of removal.
- Metrics: coverage, completion, revocation rate, repeat-offender entitlements.
- Example: a quarterly campaign covers 400 privileged entitlements; 12% are revoked, including 3 dormant admin accounts that had not been used in over a year.

## Pitfalls
- Cryptic entitlement names that force reviewers to guess — and guess "approve."
- Auto-approving overdue reviews, which converts the control into theater.
- Running the campaign but never executing the revocations.

- Reviewers bulk-approving hundreds of items in minutes; flag statistically impossible review speeds for follow-up.
- Campaigns that exclude "system" entitlements from review; service-account privilege is exactly what needs reviewing.

## References
- Saviynt documentation (docs.saviynt.com).
- NIST SP 800-53 Rev. 5, control AC-2 (account management) and AC-5 (separation of duties).
- ISACA guidance on access recertification (isaca.org) — program design.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
