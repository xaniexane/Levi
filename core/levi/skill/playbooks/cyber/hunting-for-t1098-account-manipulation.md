---
skill_id: cyber_hunting_for_t1098_account_manipulation
name: Hunting for T1098 Account Manipulation
description: Detect ATT&CK T1098 account manipulation: rogue account creation, privilege-group additions, and account-tampering across AD and cloud.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, identity, persistence]
version: 1.0.0
---
## Purpose

ATT&CK technique T1098 (Account Manipulation) covers attackers creating,
modifying, or elevating accounts to maintain access — new local admins,
domain accounts added to privileged groups, or cloud accounts granted
broad roles. This playbook provides the detection and hunting procedures
for account manipulation across Active Directory, local accounts, and
cloud identity.

## When to use

- Post-compromise: account manipulation is a primary persistence
  mechanism and must be swept before remediation is declared complete.
- Investigating privilege-escalation alerts.
- Proactive identity-hygiene hunting on a recurring cadence.
- After detecting any intrusion: assume accounts were touched until
  proven otherwise.

## Prerequisites

- AD auditing: 4720 (account created), 4728/4732/4756 (group
  additions), 4738 (account changed), 4740 (locked out — for context).
- Local account telemetry: 4720/4722 on endpoints, or EDR user-
  management visibility.
- Cloud identity audit logs: user creation, role assignments, and
  privilege grants.
- Baselines: authorized provisioning processes (HR-driven, IT
  service accounts) and privileged-group membership.

## Procedure

1. **Monitor account creation.** Alert on new accounts created outside
   the HR/IT provisioning process: 4720 events with unexpected creators,
   local accounts appearing on servers, and cloud users created outside
   SSO provisioning. Correlate creation with the creator's own
   compromise status.
2. **Monitor privilege-group changes.** Alert on additions to Domain
   Admins, Enterprise Admins, local Administrators, and cloud
   privileged roles (Global Admin, Owner) — especially additions by
   non-standard actors or outside change windows. Review the full
   privileged-group membership on a schedule, not just changes.
3. **Hunt account tampering.** Look for 4738 modifications that enable
   persistence or evasion: password-never-expires set, account
   enabled after being disabled, servicePrincipalName additions
   (Kerberoasting setup), and adminCount/SDProp-affecting changes.
4. **Check for shadow persistence accounts.** Hunt dormant-then-active
   patterns: accounts created long ago with no logons that suddenly
   authenticate, and accounts with names mimicking legitimate admins
   (typosquatting) or service accounts.
5. **Correlate with the intrusion timeline.** Tie each manipulated
   account to the attack: when was it created/modified relative to
   initial access, what did it access, and was it used for lateral
   movement or persistence? This separates attacker accounts from
   IT mistakes.
6. **Validate against provisioning records.** Every legitimate account
   should trace to a ticket or HR record — accounts without
   provenance are treated as hostile until proven otherwise.
7. **Remediate thoroughly.** Disable and investigate rogue accounts
   (do not just delete — preserve for forensics), remove unauthorized
   group memberships, reset credentials of affected accounts, and
   review what each manipulated account accessed.
8. **Harden provisioning.** Require approval workflows for privileged
   grants, alert on out-of-band account creation, enforce periodic
   privileged-access reviews, and deploy just-in-time elevation to
   shrink standing privilege.

## Expected outputs

- Account-manipulation findings with creation/modification evidence
  and attribution.
- Rogue-account inventory with forensic preservation records.
- Remediation: disabled accounts, removed memberships, resets.
- Provisioning-gap analysis and approval-workflow improvements.
- Durable detections for out-of-band account changes.

## Pitfalls

- Legitimate provisioning creates constant account-change volume —
   integrate with HR/ITSM records to auto-explain the normal flow.
- Cloud and on-prem are separate investigations — an attacker may
   manipulate both; check all identity planes.
- Deleting rogue accounts before forensic review destroys evidence —
   disable first, image/collect, then remove.
- Dormant legitimate accounts (break-glass, vendor) look like
   attacker accounts — maintain a documented inventory of them.
- Focusing only on creation: modification of existing accounts
   (privilege grants, SPN additions) is equally important.

## References

- MITRE ATT&CK: T1098 (Account Manipulation) and sub-techniques
- Microsoft Learn: AD auditing documentation (4720, 4728, 4738)
- NIST SP 800-53: account management controls (AC-2, CM-7)
- Cloud provider identity-audit documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
