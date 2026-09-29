---
skill_id: cyber_b3_golden_ticket_container_registry_azure_cloud_developing
name: Golden Ticket Attack Defense for Container Registries in Azure Cloud (Developing Maturity)
description: "Golden Ticket Attack defense playbook for Container Registries in Azure Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, containers, supply-chain, cloud, azure, maturity-developing]
version: 1.0.0
---
# Golden Ticket Attack Defense for Container Registries in Azure Cloud (Developing Maturity)

## Purpose

Forged Kerberos TGTs using the stolen krbtgt hash grant unrestricted, long-lived domain access that survives password resets. Detection relies on ticket anomalies: impossible lifetimes, wrong encryption, or logons that bypass the DC. Applies to Container Registries in Azure Cloud at Developing maturity.

## When to use

- TGTs with lifetimes far exceeding domain policy (e.g., 10 years), RC4-encrypted tickets in an AES-enforced domain, or tickets for accounts that never authenticated (no 4768).
- 4769 service-ticket requests referencing a TGT the DC never issued, or logons from hosts with no corresponding interactive session.
- The krbtgt account's own anomalous activity following a DCSync event.
- Lens: Best telemetry: push/pull audit logs + image-scan results + signature verification logs. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push/pull audit log (who pushed which tag/digest, who pulled it, from where) and Vulnerability scan results per image; signature (cosign/Notary) verification outcomes; run `reg audit log --since 7d --action push | head -30` then `reg scan results --image <image:tag> --severity high,critical`.
3. **Analyze.** Confirm via ticket inspection (klist, network capture): lifetime, encryption type, and client name mismatches prove forgery. Then: Scope everything done under forged tickets — assume full domain compromise until proven otherwise.
4. **Contain and harden.** Rotate the krbtgt password TWICE (to invalidate both current and previous hash) after any suspected compromise. Asset layer: Image signing required, immutable tags for releases, vulnerability gates blocking critical CVEs. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating krbtgt only once — the N-1 hash remains valid and the golden ticket still works.
- Treating it as an account incident instead of a domain-trust incident; the response scope is the whole forest.

## References

- MITRE ATT&CK: T1558.001 (Credential Access: Golden Ticket)
- Vendor logging and hardening baselines for Container Registries; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
