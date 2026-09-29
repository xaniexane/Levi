---
skill_id: cyber_b3_backup_tampering_vmware_esxi_azure_cloud_defined
name: Backup Tampering Defense for VMware ESXi Hosts in Azure Cloud (Defined Maturity)
description: "Backup Tampering defense playbook for VMware ESXi Hosts in Azure Cloud at Defined maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [backup, ransomware, virtualization, vmware, cloud, azure, maturity-defined]
version: 1.0.0
---
# Backup Tampering Defense for VMware ESXi Hosts in Azure Cloud (Defined Maturity)

## Purpose

Attackers delete, encrypt, or corrupt backups before the main attack so recovery is impossible. Backup systems are targeted FIRST in modern ransomware — monitor them as the crown jewels they are. Applies to VMware ESXi Hosts in Azure Cloud at Defined maturity.

## When to use

- Backup job deletions, retention policy changes, or repository credential changes outside change windows.
- Backup admin console logons from unusual accounts or hosts, or mass snapshot deletions in cloud backup vaults.
- Backup integrity check failures or sudden drops in restorable recovery points.
- Lens: Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in vCenter tasks and events (VM power ops, snapshot create/delete, host profile changes) and ESXi hostd/vpxa logs and shell-access records; VM .vmx changes; run `esxcli system auditrecords local list | tail -20` then `vim-cmd vmsvc/getallvms 2>/dev/null | head -20`.
3. **Analyze.** Determine which recovery points were destroyed versus merely marked deleted — cloud soft-delete and immutable vaults may still hold copies. Then: Identify how the attacker reached the backup system: shared credentials, unpatched console, or compromised admin.
4. **Contain and harden.** Immutable backup storage (object lock / immutable vaults) with separate credentials and MFA on the backup console. Asset layer: Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Backups on the same domain credentials as production — the attacker uses the same keys on both.
- Monitoring backup job success but never testing an actual restore.

## References

- MITRE ATT&CK: T1490 (Impact: Inhibit System Recovery)
- Vendor logging and hardening baselines for VMware ESXi Hosts; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
