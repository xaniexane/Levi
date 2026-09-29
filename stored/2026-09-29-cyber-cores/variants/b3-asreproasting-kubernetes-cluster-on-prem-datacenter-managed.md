---
skill_id: cyber_b3_asreproasting_kubernetes_cluster_on_prem_datacenter_managed
name: ASREPRoasting Defense for Kubernetes Clusters in On-Premises Datacenter (Managed Maturity)
description: "ASREPRoasting defense playbook for Kubernetes Clusters in On-Premises Datacenter at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, containers, kubernetes, on-prem, datacenter, maturity-managed]
version: 1.0.0
---
# ASREPRoasting Defense for Kubernetes Clusters in On-Premises Datacenter (Managed Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to Kubernetes Clusters in On-Premises Datacenter at Managed maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: Kubernetes audit logs + container runtime logs + admission-controller denials. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in API-server audit log (who created pods/bindings/secrets, from where) and Kubelet/container runtime logs and image pull histories per node; run `kubectl audit2rbac --filename=audit.log 2>/dev/null | head; kubectl get clusterrolebindings -o wide | head -20` then `kubectl get pods -A -o json | python3 -c "import json,sys; [print(p['metadata']['namespace'], p['metadata']['name'], p['spec'].get('hostNetwork'), p['spec'].get('hostPID')) for p in json.load(sys.stdin)['items']]" | head -30`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Least-privilege RBAC, Pod Security Standards enforced, no privileged pods, image signing/verification. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for Kubernetes Clusters; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
