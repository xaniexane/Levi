---
skill_id: cyber_b3_privilege_escalation_sudo_kubernetes_cluster_air_gapped_network_managed
name: Linux Privilege Escalation Defense for Kubernetes Clusters in Air-Gapped Networks (Managed Maturity)
description: "Linux Privilege Escalation defense playbook for Kubernetes Clusters in Air-Gapped Networks at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privilege-escalation, containers, kubernetes, air-gap, ot, high-security, maturity-managed]
version: 1.0.0
---
# Linux Privilege Escalation Defense for Kubernetes Clusters in Air-Gapped Networks (Managed Maturity)

## Purpose

Attackers turn a low-privilege Linux foothold into root via sudo misconfigurations, SUID binaries, kernel exploits, or writable service files. Harden the escalation paths and you contain most Linux intrusions at the beachhead. Applies to Kubernetes Clusters in Air-Gapped Networks at Managed maturity.

## When to use

- Sudo invocations of unusual binaries, sudoers file reads by non-admins, or successful sudo from accounts that never used it before.
- Execution of known privesc enumeration scripts (LinPEAS-style), SUID binary abuse, or kernel exploit artifacts in logs.
- New entries in sudoers.d, unexpected SUID bits, or service files modified by non-root users.
- Lens: Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in API-server audit log (who created pods/bindings/secrets, from where) and Kubelet/container runtime logs and image pull histories per node; run `kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20` then `kubectl get pods -A -o json | python3 -c "import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]" | head -30`.
3. **Analyze.** Identify the exact escalation primitive: which misconfiguration or vulnerability was used, and whether it is systemic across the fleet or host-specific. Then: Check for persistence installed with the new privileges: new SSH keys in root's authorized_keys, cron jobs, or systemd units.
4. **Contain and harden.** Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID from unnecessary binaries, and keep kernels patched. Asset layer: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the host without fixing the fleet-wide sudoers misconfiguration that enabled it.
- Assuming container escape is out of scope — check whether the foothold was a container with host mounts.

## References

- MITRE ATT&CK: T1548.003 (Privilege Escalation: Sudo and Sudo Caching)
- Vendor logging and hardening baselines for Kubernetes Clusters; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
