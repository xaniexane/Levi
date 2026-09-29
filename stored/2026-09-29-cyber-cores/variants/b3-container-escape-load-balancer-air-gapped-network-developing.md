---
skill_id: cyber_b3_container_escape_load_balancer_air_gapped_network_developing
name: Container Escape Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)
description: "Container Escape defense playbook for Load Balancers in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, network, web, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Container Escape Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)

## Purpose

A compromised container breaks out to the host via privileged mode, hostPath mounts, or kernel exploits — turning one application breach into full node control. Harden the container boundary and monitor for escape primitives. Applies to Load Balancers in Air-Gapped Networks at Developing maturity.

## When to use

- Containers running privileged or with hostPath mounts to sensitive host paths, especially created outside normal deployments.
- Host-level processes spawned by container runtimes, or unexpected writes to host paths from container contexts.
- Kernel exploit artifacts or abuse of host namespaces (nsenter-style) inside container workloads.
- Lens: Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks and Backend pool changes and health-check failure histories; run `grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15` then `echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20`.
3. **Analyze.** Determine the escape primitive: misconfiguration (privileged, hostPath, hostPID) versus kernel CVE — the fix differs. Then: Assess node compromise: if escaped, the node is hostile — cordon, drain, and rebuild it; do not trust in-place cleaning.
4. **Contain and harden.** Never run privileged containers; drop capabilities, use read-only root filesystems, and enforce via admission controllers (OPA/Kyverno). Asset layer: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rebuilding the container while the compromised node keeps serving the attacker's workloads.
- Assuming non-privileged means safe — hostPath mounts and capabilities can be equally fatal.

## References

- MITRE ATT&CK: T1611 (Escape to Host)
- Vendor logging and hardening baselines for Load Balancers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
