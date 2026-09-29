---
skill_id: cyber_b3_dll_hijacking_kubernetes_cluster_branch_office_foundational
name: DLL Hijacking Defense for Kubernetes Clusters in Branch Offices (Foundational Maturity)
description: "DLL Hijacking defense playbook for Kubernetes Clusters in Branch Offices at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, containers, kubernetes, branch, network, maturity-foundational]
version: 1.0.0
---
# DLL Hijacking Defense for Kubernetes Clusters in Branch Offices (Foundational Maturity)

## Purpose

Applications loading DLLs from insecure paths let attackers plant a malicious DLL that executes with the application's privileges. Detection focuses on DLL loads from writable directories and known-vulnerable applications. Applies to Kubernetes Clusters in Branch Offices at Foundational maturity.

## When to use

- Sysmon event 7 (image loaded) showing DLLs loaded from temp, downloads, or user-writable directories by privileged processes.
- New DLL files appearing alongside application executables, especially with names matching system DLLs.
- Application crashes or behavior changes after a DLL appears in its directory.
- Lens: Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in API-server audit log (who created pods/bindings/secrets, from where) and Kubelet/container runtime logs and image pull histories per node; run `kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20` then `kubectl get pods -A -o json | python3 -c "import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]" | head -30`.
3. **Analyze.** Verify the loading order: confirm the planted DLL shadows a legitimate one via PATH or application-directory precedence. Then: Check the DLL's exports and behavior in a sandbox — many hijack DLLs proxy the original to stay stealthy.
4. **Contain and harden.** Applications should use absolute paths and SafeDllSearchMode; remove user-writable directories from the DLL search order. Asset layer: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Deleting the DLL without fixing the insecure load order — the hole remains for the next attacker.
- Assuming signed applications are immune; the signature covers the EXE, not the DLL it loads.

## References

- MITRE ATT&CK: T1574.001 (Persistence: DLL Search Order Hijacking)
- Vendor logging and hardening baselines for Kubernetes Clusters; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
