---
skill_id: cyber_implementing_zero_standing_privilege_with_cyberark
name: Implementing Zero Standing Privilege with CyberArk
description: Eliminate persistent privileged access using CyberArk just-in-time elevation and vaulting.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, zero-trust, cyberark]
version: 1.0.0
---
## Purpose
This playbook implements zero standing privilege (ZSP): no human holds persistent admin rights. Access is vaulted in CyberArk and granted just-in-time, with approval, session recording, and automatic revocation.

## When to use
- Standing domain-admin or cloud-admin accounts exist for daily use.
- Auditors flag excessive privileged access or shared admin credentials.
- Responding to a privilege-abuse incident or insider-threat concern.

## Prerequisites
- CyberArk Privileged Access Manager deployed (Vault, PVWA, CPM, PSM).
- Inventory of privileged accounts and who uses them, mapped to business justification.
- Approval workflow owners defined (who can approve elevation requests).

## Procedure
1. **Discover and onboard accounts.** Run discovery scans, onboard privileged accounts into the Vault, and rotate them immediately to break unknown prior knowledge.
2. **Remove standing access.** Strip persistent membership in privileged groups; replace with entitlement to request elevation through CyberArk.
3. **Configure just-in-time elevation.** Define access policies: which roles may request which accounts, required approvals (manager, dual control for tier-0), and time bounds (e.g., 4-hour checkout).
4. **Enforce session isolation and recording.** Route privileged sessions through PSM with full session recording; store recordings tamper-evident with defined retention.
5. **Automate rotation.** Let the CPM rotate credentials after each checkout so no human ever knows the current password.
6. **Alert on bypass attempts.** Monitor for direct logons to vaulted accounts, disabled CPM management, or PSM bypass — these are high-severity detections.
7. **Review entitlements quarterly.** Recertify who may request elevation; remove stale entitlements the same day someone changes roles.

8. **Cover service and application accounts.** Extend vaulting and rotation to non-human privileged accounts; attackers love the service account nobody rotates.
9. **Test the break-glass path.** Exercise emergency access procedures in drills so they work during a real incident when the normal workflow is unavailable.

## Expected outputs
- Zero accounts with standing privileged access for interactive use; all elevation via CyberArk.
- Approval workflows, session recordings, and post-checkout rotation verified.
- Quarterly entitlement recertification records.
- Example: a database administrator requests 4-hour production access, gets manager approval, works through a recorded PSM session, and the credential auto-rotates on checkout — with no standing DBA rights remaining.

## Pitfalls
- Break-glass accounts left unmanaged: they must exist, be vaulted, sealed, and monitored — not forgotten.
- Approval workflows so slow that teams build shadow admin paths around them.
- Onboarding accounts but leaving the old shared passwords in circulation.

- Vaulting credentials but leaving the same accounts usable via cached credentials or Kerberos tickets on endpoints; rotation must invalidate all forms of the credential.
- Approval workflows with a single approver who is also the requester for "urgent" cases; separation of duties must survive urgency.

## References
- CyberArk Privileged Access Manager documentation (docs.cyberark.com).
- NIST SP 800-53 Rev. 5, controls AC-2, AC-5, AC-6 (account and privilege management).
- CISA privileged access guidance (cisa.gov) — PAM best practices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
