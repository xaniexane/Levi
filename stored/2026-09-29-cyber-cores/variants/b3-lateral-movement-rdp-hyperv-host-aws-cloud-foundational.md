---
skill_id: cyber_b3_lateral_movement_rdp_hyperv_host_aws_cloud_foundational
name: RDP Lateral Movement Defense for Hyper-V Hosts in AWS Cloud (Foundational Maturity)
description: "RDP Lateral Movement defense playbook for Hyper-V Hosts in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, virtualization, hyperv, cloud, aws, maturity-foundational]
version: 1.0.0
---
# RDP Lateral Movement Defense for Hyper-V Hosts in AWS Cloud (Foundational Maturity)

## Purpose

RDP is both an admin tool and the attacker's favorite lateral highway. Compromised credentials plus unrestricted RDP equals domain-wide movement that looks almost legitimate in the logs. Applies to Hyper-V Hosts in AWS Cloud at Foundational maturity.

## When to use

- 4624 type-10 (RDP) logons from a workstation to servers or other workstations outside the user's normal admin pattern.
- RDP sessions at unusual hours, from hosts the account never logged into before, or with clipboard/drive redirection moving tools onto the target.
- TerminalServices-LocalSessionManager events (21/25) on targets without a matching helpdesk ticket or change record.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Correlate RDP logons with the source host's compromise timeline to distinguish attacker sessions from legitimate admin work. Then: Check for credential harvesting on each RDP target: LSASS access or SAM reads following the session indicate theft.
4. **Contain and harden.** RDP restricted to jump hosts/bastions with MFA; Network Level Authentication enforced; no direct workstation-to-server RDP. Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Allowing 'temporary' RDP exceptions that become permanent lateral paths.
- Missing RDP-based movement because you only hunted SMB — attackers use whatever is open.

## References

- MITRE ATT&CK: T1021.001 (Lateral Movement: Remote Desktop Protocol)
- Vendor logging and hardening baselines for Hyper-V Hosts; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
