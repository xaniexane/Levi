---
skill_id: cyber_b3_watering_hole_hyperv_host_air_gapped_network_developing
name: Watering Hole Attack Defense for Hyper-V Hosts in Air-Gapped Networks (Developing Maturity)
description: "Watering Hole Attack defense playbook for Hyper-V Hosts in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, virtualization, hyperv, windows, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Watering Hole Attack Defense for Hyper-V Hosts in Air-Gapped Networks (Developing Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to Hyper-V Hosts in Air-Gapped Networks at Developing maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: Hyper-V-VMMS/Hyper-V-Worker event logs + host Security log + SCVMM job history. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Microsoft-Windows-Hyper-V-VMMS event log (VM create/start/stop, checkpoint ops) and Virtual switch and virtual NIC configuration; VM configuration files and checkpoints; run `Get-WinEvent -LogName 'Microsoft-Windows-Hyper-V-VMMS-Admin' -MaxEvents 25 | Select-Object TimeCreated, Id, Message | Format-Table -Wrap` then `Get-VM | Select-Object Name, State, CheckpointType, @{n='Switch';e={(Get-VMNetworkAdapter $_).SwitchName}} | Format-Table`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: Dedicated management NIC/vLAN, Shielded VMs for sensitive workloads, guarded fabric where available. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for Hyper-V Hosts; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
