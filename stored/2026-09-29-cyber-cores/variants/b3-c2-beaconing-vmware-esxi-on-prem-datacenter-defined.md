---
skill_id: cyber_b3_c2_beaconing_vmware_esxi_on_prem_datacenter_defined
name: C2 Beaconing Defense for VMware ESXi Hosts in On-Premises Datacenter (Defined Maturity)
description: "C2 Beaconing defense playbook for VMware ESXi Hosts in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, c2, virtualization, vmware, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# C2 Beaconing Defense for VMware ESXi Hosts in On-Premises Datacenter (Defined Maturity)

## Purpose

Compromised hosts check in with attacker infrastructure on a schedule — the heartbeat of an intrusion. Beaconing detection is statistical: regularity, jitter analysis, and connection uniformity reveal what signatures miss. Applies to VMware ESXi Hosts in On-Premises Datacenter at Defined maturity.

## When to use

- Outbound connections at fixed intervals (e.g., every 60s) with consistent byte counts to an external host — visible in NetFlow or proxy logs as metronomic traffic.
- Long-lived sessions to IPs with no domain, newly registered domains, or domains with no legitimate business purpose.
- Jittered but statistically regular timing: inter-arrival times clustering around a mean with small variance.
- Lens: Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in vCenter tasks and events (VM power ops, snapshot create/delete, host profile changes) and ESXi hostd/vpxa logs and shell-access records; VM .vmx changes; run `esxcli system auditrecords local list | tail -20` then `vim-cmd vmsvc/getallvms 2>/dev/null | head -20`.
3. **Analyze.** Compute inter-arrival statistics on the suspect flows; true beacons show low variance even with jitter, unlike human browsing. Then: Capture the beacon payload in a sandbox detonation to identify the implant family and its tasking protocol.
4. **Contain and harden.** Egress filtering: default-deny outbound with allowlisted destinations for servers; alert on direct-to-IP connections. Asset layer: Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Chasing the C2 IP instead of the implant — infrastructure is disposable, the foothold is what matters.
- Assuming encrypted traffic cannot be analyzed: timing, size, and destination metadata still betray beacons.

## References

- MITRE ATT&CK: T1071.001 (Command and Control: Web Protocols)
- Vendor logging and hardening baselines for VMware ESXi Hosts; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
