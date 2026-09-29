---
skill_id: cyber_b3_kerberoasting_backup_server_hybrid_cloud_developing
name: Kerberoasting Defense for Backup Servers in Hybrid Cloud (Developing Maturity)
description: "Kerberoasting defense playbook for Backup Servers in Hybrid Cloud at Developing maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, backup, ransomware, hybrid, cloud, on-prem, maturity-developing]
version: 1.0.0
---
# Kerberoasting Defense for Backup Servers in Hybrid Cloud (Developing Maturity)

## Purpose

Attackers request service tickets for SPN accounts and crack them offline to recover service-account passwords — no alerts on the DC, because requesting tickets is normal. The defense is making those passwords uncrackable and the requests visible. Applies to Backup Servers in Hybrid Cloud at Developing maturity.

## When to use

- A single account requesting an unusual number of service tickets (4769) with RC4 encryption for many different SPNs in a short window.
- Ticket requests for SPNs from accounts with no business need, or requests at odd hours from a workstation (not a server).
- Subsequent use of a cracked service account: logons from unexpected hosts or privilege changes for that account.
- Lens: Best telemetry: job audit logs + admin-console access logs + integrity-check results. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Backup job definitions, run histories, and deletion/retention-change audit entries and Admin console logons and configuration exports; repository credential-change history; run `# conceptually (product CLIs differ):` then `backup-cli jobs list --failed --last 7d`.
3. **Analyze.** List every SPN targeted and assess the crackability of each service account's password (length, complexity, age). Then: If a service account was cracked, treat it as full compromise: inventory everything that account could touch.
4. **Contain and harden.** Service accounts: 25+ character random passwords, or better, group Managed Service Accounts (gMSA) with automatic rotation. Asset layer: Immutable storage, separate admin credentials with MFA, no domain-joined backup console if avoidable. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the password but leaving the SPN on a weak account — the attacker just roasts it again.
- Missing that the cracked service account may have been used to request MORE tickets (roast chaining).

## References

- MITRE ATT&CK: T1558.003 (Credential Access: Kerberoasting)
- Vendor logging and hardening baselines for Backup Servers; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
