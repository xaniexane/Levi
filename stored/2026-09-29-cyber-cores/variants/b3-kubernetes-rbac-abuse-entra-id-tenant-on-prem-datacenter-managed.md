---
skill_id: cyber_b3_kubernetes_rbac_abuse_entra_id_tenant_on_prem_datacenter_managed
name: Kubernetes RBAC Abuse Defense for Microsoft Entra ID Tenants in On-Premises Datacenter (Managed Maturity)
description: "Kubernetes RBAC Abuse defense playbook for Microsoft Entra ID Tenants in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [containers, kubernetes, identity, cloud, microsoft, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# Kubernetes RBAC Abuse Defense for Microsoft Entra ID Tenants in On-Premises Datacenter (Managed Maturity)

## Purpose

Overly broad Kubernetes roles let attackers escalate from a compromised pod to cluster admin. RBAC misconfigurations are the Kubernetes equivalent of AD delegation sprawl — audit them the same way. Applies to Microsoft Entra ID Tenants in On-Premises Datacenter at Managed maturity.

## When to use

- Pods or service accounts using cluster-admin or wildcard roles, especially ones created outside GitOps pipelines.
- Kubernetes audit logs showing service accounts listing secrets cluster-wide or creating privileged pods.
- New ClusterRoleBindings granting powerful roles to default or application service accounts.
- Lens: Best telemetry: Entra sign-in + audit logs streamed to Log Analytics/SIEM with 30+ day retention. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Sign-in logs (interactive, non-interactive, service principal) with risk detections and MFA details and Audit logs: app registrations, consent grants, Conditional Access changes, role assignments; run `# Microsoft Graph (delegated admin): recent risky sign-ins` then `Get-MgAuditLogSignIn -Filter "riskState eq 'atRisk'" -Top 25 | Select-Object CreatedDateTime, UserPrincipalName, IpAddress, @{n='Risk';e={$_.RiskDetail}}`.
3. **Analyze.** Map effective permissions per service account: which can read secrets, create pods, or exec into others — that is the blast radius. Then: Check whether the abused binding was created by the attacker or pre-existing misconfiguration.
4. **Contain and harden.** Least-privilege RBAC, no wildcards, no cluster-admin for apps; manage bindings via GitOps with PR review. Asset layer: Conditional Access: require phishing-resistant MFA, compliant devices, block legacy auth and risky sign-ins. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the abused binding but leaving 50 other wildcard roles in place.
- Forgetting that a compromised pod with cloud credentials can pivot from k8s RBAC to cloud IAM.

## References

- MITRE ATT&CK: T1609 (Container Administration Command)
- Vendor logging and hardening baselines for Microsoft Entra ID Tenants; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
