---
skill_id: cyber_implementing_azure_ad_privileged_identity_management
name: Privileged Identity Management in Microsoft Entra ID
description: Eliminate standing privilege with Entra PIM: just-in-time elevation, approvals, and access reviews.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, azure]
version: 1.0.0
---
## Purpose
Standing privileged accounts — admins who are always admins — are the attacker's dream: compromise
one account, own the tenant. Privileged Identity Management (PIM) in Microsoft Entra ID converts
privilege to just-in-time: eligible assignments, MFA-gated activation with justification, time
limits, and approvals. This playbook implements PIM to reach zero standing privilege for Entra and
Azure roles.

## When to use
- Removing permanent Global Administrator and privileged role assignments.
- After incidents or audits flagging excessive standing admin access.
- Meeting PAM requirements for SOC 2, ISO 27001, PCI DSS, or cyber-insurance questionnaires.
- Before or during an Entra ID tenant security hardening program.
- As the identity-plane complement to endpoint privilege management.

## Prerequisites
- Entra ID P2 licensing for PIM features.
- Inventory of current privileged role assignments (Entra roles and Azure RBAC): who holds what,
  permanently vs. eligible.
- Defined approvers per role: managers or security staff who can judge activation requests promptly.
- MFA enforced for all privileged users (activation requires it — no exceptions).
- Break-glass emergency accounts created, monitored, and excluded from PIM (documented separately).

## Procedure
1. **Inventory standing privilege.** Export all permanent assignments for Entra ID roles (Global
   Administrator, Privileged Authentication Administrator, etc.) and Azure RBAC (Owner, Contributor,
   User Access Administrator). Classify each as: still needed (convert to eligible), needed rarely
   (eligible with approval), or unneeded (remove).
2. **Convert permanent to eligible.** Change assignments from permanent Active to Eligible with
   maximum activation duration (start with 8 hours; tighten to 4 or less for the most sensitive
   roles). Require MFA, justification, and ticket number on activation.
3. **Require approval for sensitive roles.** Configure approval workflows for Global Administrator,
   Privileged Role Administrator, and Azure Owner: designated approvers, SLA for decisions, and no
   self-approval. Less sensitive roles can use eligible-without-approval initially, then add
   approval as the culture adapts.
4. **Set activation policies tightly.** Require: Azure MFA, justification, and (where supported)
   conditional-access-compliant device or location. Set activation max duration short; disable
   permanent eligible assignments beyond the policy window via reviews.
5. **Protect the break-glass accounts.** Two emergency access accounts, long random passwords in
   sealed storage, excluded from Conditional Access and PIM, monitored with alerts on any sign-in.
   Test them quarterly. Document that these are the only standing privileged accounts and why they
   exist.
6. **Enable access reviews.** Schedule quarterly reviews of all eligible assignments: reviewers
   confirm continued need. Auto-remove on deny or non-response (configure to remove access when
   reviewers don't respond — the secure default).
7. **Alert on PIM events.** Send to the SIEM and alert on: activations outside business hours,
   activations without corresponding change tickets, approval denials followed by re-requests,
   break-glass sign-ins, and PIM policy changes. Activation without a ticket is an investigation
   trigger.
8. **Extend to Azure resources and groups.** Apply PIM to Azure RBAC roles on subscriptions/resource
   groups and to privileged security groups (eligible group membership). Privilege hiding in groups
   is the classic PIM bypass — cover it.
9. **Run a privilege-fire drill.** Quarterly: have an admin activate a role, perform a task, and
   confirm auto-expiry revokes access. Verify alerts fired and the audit log captured the full
   lifecycle. Document the drill as control evidence.
10. **Report privilege posture.** Monthly: count of standing vs. eligible assignments (target: zero
    standing except break-glass), activation volume and after-hours rate, access-review completion,
    and mean approval time. Trend toward less privilege, faster legitimate access.

## Expected outputs
- All privileged roles converted to eligible with MFA, justification, and time limits; approvals on
  sensitive roles.
- Break-glass accounts secured, monitored, and tested.
- Quarterly access reviews with auto-removal on non-response.
- SIEM alerting on anomalous activations and PIM policy changes.
- Monthly privilege-posture metrics trending to zero standing access.

## Pitfalls
- Converting to eligible without approvals or short durations: "eligible forever with one click" is
  barely better than standing. Approvals and short windows are the control.
- Forgetting Azure RBAC and privileged groups: attackers use whatever privilege path remains — PIM
  must cover Entra roles, Azure roles, and group memberships.
- Approvers who rubber-stamp: train approvers to verify the ticket and need; audit approval
  decisions periodically.
- No break-glass plan: if PIM or Conditional Access misconfigures and locks everyone out, you need
  tested emergency access. Untested break-glass is a hope.
- Licensing gaps: PIM requires P2 — ensure all privileged users are licensed or the control silently
  doesn't apply to them.

## References
- Microsoft Learn: Microsoft Entra Privileged Identity Management documentation
- Microsoft Learn: emergency access (break-glass) accounts guidance
- NIST SP 800-53 AC-6 (least privilege), AC-2 (account management)
- MITRE ATT&CK T1078 (Valid Accounts) — what JIT privilege constrains
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
