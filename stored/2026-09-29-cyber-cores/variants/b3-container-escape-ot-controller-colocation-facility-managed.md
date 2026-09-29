---
skill_id: cyber_b3_container_escape_ot_controller_colocation_facility_managed
name: Container Escape Defense for OT Controllers in Colocation Facilities (Managed Maturity)
description: "Container Escape defense playbook for OT Controllers in Colocation Facilities at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, ot, ics, critical-infrastructure, on-prem, colocation, maturity-managed]
version: 1.0.0
---
# Container Escape Defense for OT Controllers in Colocation Facilities (Managed Maturity)

## Purpose

A compromised container breaks out to the host via privileged mode, hostPath mounts, or kernel exploits — turning one application breach into full node control. Harden the container boundary and monitor for escape primitives. Applies to OT Controllers in Colocation Facilities at Managed maturity.

## When to use

- Containers running privileged or with hostPath mounts to sensitive host paths, especially created outside normal deployments.
- Host-level processes spawned by container runtimes, or unexpected writes to host paths from container contexts.
- Kernel exploit artifacts or abuse of host namespaces (nsenter-style) inside container workloads.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Determine the escape primitive: misconfiguration (privileged, hostPath, hostPID) versus kernel CVE — the fix differs. Then: Assess node compromise: if escaped, the node is hostile — cordon, drain, and rebuild it; do not trust in-place cleaning.
4. **Contain and harden.** Never run privileged containers; drop capabilities, use read-only root filesystems, and enforce via admission controllers (OPA/Kyverno). Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rebuilding the container while the compromised node keeps serving the attacker's workloads.
- Assuming non-privileged means safe — hostPath mounts and capabilities can be equally fatal.

## References

- MITRE ATT&CK: T1611 (Escape to Host)
- Vendor logging and hardening baselines for OT Controllers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
