---
skill_id: cyber_performing_service_account_audit
name: Service Account Audit
description: Audit service accounts for over-privilege, stale credentials, and missing ownership to shrink a high-risk attack surface.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, service-accounts, audit]
version: 1.0.0
---

## Purpose
- Build an accurate inventory of service accounts, which are often invisible to standard access reviews.
- Find over-privileged, orphaned, and interactively-usable service accounts.
- Assign ownership and lifecycle management to every service account.

## When to use
- During identity security assessments and privileged access reviews.
- When incidents involve service account compromise or misuse.
- Before migrating authentication systems or directory services.
- As a recurring control, typically semi-annually.

## Prerequisites
- Directory and cloud IAM read access sufficient to enumerate service accounts.
- A definition of what qualifies as a service account in each environment.
- Log access to assess actual usage: last logon, authentication patterns, and source systems.
- Stakeholder contacts in application teams who can confirm business need.

## Procedure
1. Enumerate service accounts across directories, cloud IAM, databases, and key applications.
2. Classify each account: application service, scheduled task, monitoring, backup, or unknown.
3. Verify ownership: every account needs a named human or team owner accountable for it.
4. Review privileges against actual usage; flag accounts with admin rights they never exercise.
5. Check credential hygiene: password age, rotation history, and whether the credential is shared or embedded in code.
6. Flag service accounts with interactive logon rights, which should be rare and justified.
7. Identify orphaned accounts tied to decommissioned applications or departed owners.
8. Check for service accounts excluded from MFA or conditional access policies without documented justification.
9. Recommend remediation per account: deprivilege, vault the credential, assign ownership, or decommission.
10. Migrate eligible accounts to managed identities or group managed service accounts where the platform supports it.
11. Verify changes in a maintenance window and monitor for application breakage.
12. Establish the recurring audit cadence with automated discovery feeding it.

## Expected outputs
- A service account inventory with ownership, classification, and risk ratings.
- Remediation actions per account with verification.
- A recurring audit process with automated discovery.
- A service account standard defining naming, ownership, and lifecycle requirements.
- Integration of service accounts into the regular access recertification cycle.

## Pitfalls
- Disabling a service account before mapping its dependencies; outages follow quickly.
- Auditing directory accounts while missing cloud, database, and SaaS service accounts.
- Accepting vendor claims that an account needs domain admin without verifying actual usage.
- Treating the audit as one-time; service accounts accumulate again within months.

## References
- NIST SP 800-53 control AC-2 on account management
- NIST SP 800-53 access control family
- Microsoft Learn guidance on managed service accounts
- CIS Controls on account management
- Vendor documentation for managed identities in the cloud platforms used
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
