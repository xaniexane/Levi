---
skill_id: cyber_b3_cryptominer_intrusion_kubernetes_cluster_azure_cloud_developing
name: Cryptominer Intrusion Defense for Kubernetes Clusters in Azure Cloud (Developing Maturity)
description: "Cryptominer Intrusion defense playbook for Kubernetes Clusters in Azure Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [malware, cloud, containers, kubernetes, azure, maturity-developing]
version: 1.0.0
---
# Cryptominer Intrusion Defense for Kubernetes Clusters in Azure Cloud (Developing Maturity)

## Purpose

Unauthorized miners burn CPU/GPU and cloud spend, and — more importantly — prove an attacker has code execution on your assets. Treat every miner as a foothold to investigate, not just a performance problem. Applies to Kubernetes Clusters in Azure Cloud at Developing maturity.

## When to use

- Sustained high CPU/GPU on hosts or cloud instances with no business workload, especially at night/weekends, plus connections to known mining pools on Stratum ports.
- Cloud billing spikes for compute in regions you do not use, or new instances launched by unfamiliar principals.
- EDR detections for xmrig or similar binaries, scheduled tasks re-fetching miner payloads, or WMI persistence entries.
- Lens: Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in API-server audit log (who created pods/bindings/secrets, from where) and Kubelet/container runtime logs and image pull histories per node; run `kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20` then `kubectl get pods -A -o json | python3 -c "import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]" | head -30`.
3. **Analyze.** Trace the miner's persistence and delivery: the initial access vector (exposed service, weak SSH, vulnerable app) matters more than the miner itself. Then: Check for dual-use: many miner campaigns also exfiltrate credentials or deploy additional payloads — sweep for those.
4. **Contain and harden.** Close the entry vector (patch the exploited service, enforce key-based SSH, remove internet exposure), then block mining pool domains at DNS. Asset layer: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the miner without removing persistence — it returns on reboot or on schedule.
- Writing it off as 'just a miner' without investigating the initial access that delivered it.

## References

- MITRE ATT&CK: T1496 (Impact: Resource Hijacking)
- Vendor logging and hardening baselines for Kubernetes Clusters; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
