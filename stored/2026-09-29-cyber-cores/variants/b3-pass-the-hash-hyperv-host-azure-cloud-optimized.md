---
skill_id: cyber_b3_pass_the_hash_hyperv_host_azure_cloud_optimized
name: Pass-the-Hash Defense for Hyper-V Hosts in Azure Cloud (Optimized Maturity)
description: "Pass-the-Hash defense playbook for Hyper-V Hosts in Azure Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, lateral-movement, virtualization, hyperv, windows, cloud, azure, maturity-optimized]
version: 1.0.0
---
# Pass-the-Hash Defense for Hyper-V Hosts in Azure Cloud (Optimized Maturity)

## Purpose

Stolen NTLM hashes authenticate without the password ever being cracked. It is invisible to password monitoring because no password is used — defense means killing NTLM where possible and watching for its telltale logon patterns. Applies to Hyper-V Hosts in Azure Cloud at Optimized maturity.

## When to use

- 4624 type-3/9 logons using NTLM where Kerberos is expected, especially from workstations to servers with admin accounts.
- Logon sessions with no interactive activity but successful authentication, or the same hash authenticating from multiple hosts simultaneously.
- NTLM audit logs showing authentication for accounts that should be Kerberos-only.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Determine hash source: LSASS dump, SAM extraction, or DCSync — each implies a different prior compromise to remediate. Then: List every host the hash authenticated to; each is a foothold until reimaged or verified clean.
4. **Contain and harden.** Reduce NTLM usage (audit mode first, then restrict), deploy Credential Guard, and use unique local admin passwords (LAPS). Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without considering that the attacker may have dumped the NEW hash too if still present.
- Disabling NTLM blindly and breaking legacy apps — audit first, restrict second.

## References

- MITRE ATT&CK: T1550.002 (Lateral Movement: Pass the Hash)
- Vendor logging and hardening baselines for Hyper-V Hosts; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
