---
skill_id: cyber_b3_container_escape_saas_application_air_gapped_network_defined
name: Container Escape Defense for SaaS Applications in Air-Gapped Networks (Defined Maturity)
description: "Container Escape defense playbook for SaaS Applications in Air-Gapped Networks at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, cloud, saas, identity, air-gap, ot, high-security, maturity-defined]
version: 1.0.0
---
# Container Escape Defense for SaaS Applications in Air-Gapped Networks (Defined Maturity)

## Purpose

A compromised container breaks out to the host via privileged mode, hostPath mounts, or kernel exploits — turning one application breach into full node control. Harden the container boundary and monitor for escape primitives. Applies to SaaS Applications in Air-Gapped Networks at Defined maturity.

## When to use

- Containers running privileged or with hostPath mounts to sensitive host paths, especially created outside normal deployments.
- Host-level processes spawned by container runtimes, or unexpected writes to host paths from container contexts.
- Kernel exploit artifacts or abuse of host namespaces (nsenter-style) inside container workloads.
- Lens: Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Admin audit log (settings changes, user provisioning, sharing changes) and User activity logs: file access, downloads, external sharing events; run `# conceptually (SaaS APIs differ):` then `saas-cli audit log --category admin --last 7d --format table | head -25`.
3. **Analyze.** Determine the escape primitive: misconfiguration (privileged, hostPath, hostPID) versus kernel CVE — the fix differs. Then: Assess node compromise: if escaped, the node is hostile — cordon, drain, and rebuild it; do not trust in-place cleaning.
4. **Contain and harden.** Never run privileged containers; drop capabilities, use read-only root filesystems, and enforce via admission controllers (OPA/Kyverno). Asset layer: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rebuilding the container while the compromised node keeps serving the attacker's workloads.
- Assuming non-privileged means safe — hostPath mounts and capabilities can be equally fatal.

## References

- MITRE ATT&CK: T1611 (Escape to Host)
- Vendor logging and hardening baselines for SaaS Applications; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
