---
skill_id: cyber_b3_golden_ticket_code_repository_azure_cloud_developing
name: Golden Ticket Attack Defense for Code Repositories in Azure Cloud (Developing Maturity)
description: "Golden Ticket Attack defense playbook for Code Repositories in Azure Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, devops, supply-chain, secrets, cloud, azure, maturity-developing]
version: 1.0.0
---
# Golden Ticket Attack Defense for Code Repositories in Azure Cloud (Developing Maturity)

## Purpose

Forged Kerberos TGTs using the stolen krbtgt hash grant unrestricted, long-lived domain access that survives password resets. Detection relies on ticket anomalies: impossible lifetimes, wrong encryption, or logons that bypass the DC. Applies to Code Repositories in Azure Cloud at Developing maturity.

## When to use

- TGTs with lifetimes far exceeding domain policy (e.g., 10 years), RC4-encrypted tickets in an AES-enforced domain, or tickets for accounts that never authenticated (no 4768).
- 4769 service-ticket requests referencing a TGT the DC never issued, or logons from hosts with no corresponding interactive session.
- The krbtgt account's own anomalous activity following a DCSync event.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Confirm via ticket inspection (klist, network capture): lifetime, encryption type, and client name mismatches prove forgery. Then: Scope everything done under forged tickets — assume full domain compromise until proven otherwise.
4. **Contain and harden.** Rotate the krbtgt password TWICE (to invalidate both current and previous hash) after any suspected compromise. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating krbtgt only once — the N-1 hash remains valid and the golden ticket still works.
- Treating it as an account incident instead of a domain-trust incident; the response scope is the whole forest.

## References

- MITRE ATT&CK: T1558.001 (Credential Access: Golden Ticket)
- Vendor logging and hardening baselines for Code Repositories; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
