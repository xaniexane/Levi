---
skill_id: cyber_b3_lateral_movement_smb_hyperv_host_azure_cloud_optimized
name: SMB Lateral Movement Defense for Hyper-V Hosts in Azure Cloud (Optimized Maturity)
description: "SMB Lateral Movement defense playbook for Hyper-V Hosts in Azure Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, virtualization, hyperv, cloud, azure, maturity-optimized]
version: 1.0.0
---
# SMB Lateral Movement Defense for Hyper-V Hosts in Azure Cloud (Optimized Maturity)

## Purpose

Attackers move host-to-host over SMB using stolen credentials — PsExec-style service creation, admin shares, or WMI. In a flat network, one compromised workstation becomes the whole domain in hours. Applies to Hyper-V Hosts in Azure Cloud at Optimized maturity.

## When to use

- SMB sessions from a workstation to many other hosts in a short window, especially to ADMIN$ or C$ shares the user never touches normally.
- Service creation events (7045) with service binaries in ADMIN$\system32, or 4624 type-3 logons with the same account across dozens of hosts.
- EDR process trees showing services.exe spawning cmd/powershell shortly after a remote SMB session.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Map the movement graph: source host, credential used, target hosts, timestamps — this is the incident's skeleton. Then: Determine which credential enabled it (stolen hash, ticket, or plaintext) to know what must be rotated enterprise-wide.
4. **Contain and harden.** Segment the network (workstation-to-workstation SMB blocked), deploy LAPS for unique local admin passwords, and restrict lateral logon rights via tiered admin model. Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning patient zero while the attacker's beachheads on hosts 3, 7, and 12 remain active.
- Rotating the compromised account's password but not the kerberos tickets/hashes already stolen from it.

## References

- MITRE ATT&CK: T1021.002 (Lateral Movement: SMB/Windows Admin Shares)
- Vendor logging and hardening baselines for Hyper-V Hosts; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
