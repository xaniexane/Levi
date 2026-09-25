---
skill_id: cyber_implementing_just_in_time_access_provisioning
name: Implementing Just-in-Time Access Provisioning
description: Replace standing privileged access with time-bound, approval-gated just-in-time elevation that grants least privilege for a defined window and revokes automatically.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, pam, access-control, zero-trust]
version: 1.0.0
---
## Purpose

Eliminate standing privileged access — the standing domain-admin, the always-on production database role, the permanent "break-glass" cloud admin — by moving to just-in-time (JIT) provisioning: users hold no privilege by default, request elevation for a specific task and duration, get approved (human or policy), and lose the access automatically when the window closes. Every grant is logged, scoped, and temporary.

## When to use

- Reducing the blast radius of compromised credentials, the single most common privilege-escalation path.
- Meeting requirements for privileged access management (PCI DSS 4.0 Req 7/8, ISO 27001 A.5.15–5.18, SOX IT controls).
- Replacing shared admin accounts and static sudoers entries with attributable, temporary elevation.
- Supporting contractors, vendors, and on-call engineers who need occasional production access.
- Post-incident, when investigation shows the attacker lived off long-lived privileged access.

## Prerequisites

- Inventory of privileged access: who holds it, where (AD, cloud IAM, databases, SaaS admin roles), and why.
- An identity provider and a PAM or identity-governance platform capable of temporary grants (Entra PIM, CyberArk, native cloud IAM with time-bound policies, Teleport, etc.).
- Defined approval workflows: who approves which elevations, with backup approvers and emergency paths.
- Ticketing/change integration so routine elevations reference a change or incident ticket.
- SIEM ingestion of grant/deny/expire events before go-live — JIT without monitoring is just slower standing access.

## Procedure

1. **Inventory and classify privileged access.** List every standing privileged grant across AD (Domain Admins, etc.), cloud (IAM admin policies), databases, and SaaS. Classify each as eligible for JIT, requiring redesign, or genuinely needing persistence (with documented justification and compensating controls).
2. **Remove standing privilege first where trivially safe.** Convert obvious cases immediately: personal admin accounts become standard users, shared accounts get individual accountability, static cloud admin policies detach. Measure the standing-privilege count as your headline metric.
3. **Define elevation catalogs.** For each system, define the roles available for JIT request: what permissions each carries, maximum duration (e.g., 4 hours for routine, 1 hour for domain-level), and whether it needs approval or is auto-approved for eligible users. Keep the catalog small — twenty roles nobody understands will be bypassed.
4. **Build the request-approve-grant flow.** Users request via the PAM portal, chatops, or CLI; the system checks eligibility (group membership, MFA, device posture, ticket reference), routes to approvers for sensitive roles, provisions the grant with an expiry, and notifies. Auto-approve low-risk, time-bound elevations for on-call staff to avoid the workflow becoming the outage.
5. **Enforce automatic revocation.** Expiry must be technical, not procedural: the IAM policy detaches, the AD group membership lapses, the database role drops — without human action. Test revocation under failure conditions (approver offline, system clock skew) and alert on grants that outlive their window.
6. **Log everything to the SIEM.** Emit request, approval, activation, and expiry events with requester, approver, ticket, scope, and duration. Build detections for anomalous patterns: repeated denied requests, elevations outside on-call hours, and privilege use inconsistent with the stated ticket.
7. **Handle break-glass.** Maintain a tiny set of emergency accounts with split-knowledge credentials, sealed and monitored — any use pages the security team. Test the break-glass path quarterly; an untested emergency account is a hope, not a control.
8. **Review and tighten.** Monthly, review the elevation catalog usage: unused roles get removed, frequently extended durations get questioned, and repeat requesters for the same task become candidates for redesigned (narrower, permanent, heavily monitored) access or automation that removes the human need.

## Expected outputs

- Privileged-access inventory with JIT eligibility classification.
- Elevation catalog with durations, approval tiers, and owners.
- Working request/approve/grant/revoke automation with tested expiry.
- SIEM detections on elevation anomalies and break-glass use.
- Monthly metrics: standing-privilege count, elevation volume, approval times, expired-grant compliance.

## Pitfalls

- **Approval bottlenecks during incidents.** If the on-call engineer cannot get production access at 3 a.m. without waking three approvers, they will build backdoors. Auto-approve for eligible on-call with strong post-hoc review.
- **Expiry that requires a human.** "Please remember to remove the access" is standing access with extra steps. Revocation must be automatic and verified.
- **Ticket-reference theater.** Requiring a ticket number that nobody validates just adds a text field. Spot-check ticket legitimacy for sensitive elevations.
- **Forgetting service accounts.** JIT for humans while service accounts keep permanent domain-admin rights leaves the largest attack surface untouched. Bring service accounts into the PAM vault with rotation.
- **MFA gaps on the elevation path.** JIT that can be requested from a session authenticated with weak MFA is a privilege-escalation shortcut. Require phishing-resistant MFA for elevation requests.

## References

- Microsoft Entra Privileged Identity Management documentation — https://learn.microsoft.com/en-us/entra/id-governance/privileged-identity-management/pim-configure
- NIST SP 800-53 Rev. 5, AC-2 (Account Management) and AC-6 (Least Privilege) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- MITRE ATT&CK T1078 (Valid Accounts) — https://attack.mitre.org/techniques/T1078/
- CISA guidance on eliminating standing privilege in identity systems
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
