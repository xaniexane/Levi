---
skill_id: cyber_b3_dcsync_attack_hyperv_host_remote_workforce_managed
name: DCSync Attack Defense for Hyper-V Hosts in Remote Workforce (Managed Maturity)
description: "DCSync Attack defense playbook for Hyper-V Hosts in Remote Workforce at Managed maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, virtualization, hyperv, windows, remote, endpoint, zero-trust, maturity-managed]
version: 1.0.0
---
# DCSync Attack Defense for Hyper-V Hosts in Remote Workforce (Managed Maturity)

## Purpose

With replication rights, an attacker impersonates a domain controller and pulls password hashes for ANY account — including krbtgt — via normal replication traffic. It looks like DC-to-DC chatter, which is why it evades naive monitoring. Applies to Hyper-V Hosts in Remote Workforce at Managed maturity.

## When to use

- 4662 (directory object access) on the domain root or krbtgt account by a principal that is not a real domain controller.
- Replication traffic (DRS) originating from a non-DC host, or a DC requesting replication far outside the normal schedule.
- Newly granted DS-Replication-Get-Changes rights (especially Get-Changes-All) to users, groups, or computers.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Identify which account performed the sync and which hashes were pulled — a krbtgt pull means the entire domain's Kerberos trust must be reset (double krbtgt rotation). Then: Review how the attacker gained replication rights: compromised admin, delegated rights sprawl, or ACL abuse.
4. **Contain and harden.** Audit and strip replication rights to the minimum; alert on any grant of Get-Changes-All. Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting user passwords but not the krbtgt — golden tickets forged from a stolen krbtgt survive password resets.
- Missing that DCSync needs only replication rights, not Domain Admin — delegated-rights sprawl is the usual enabler.

## References

- MITRE ATT&CK: T1003.006 (Credential Access: DCSync)
- Vendor logging and hardening baselines for Hyper-V Hosts; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
