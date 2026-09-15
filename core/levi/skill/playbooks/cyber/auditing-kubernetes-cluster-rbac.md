---
skill_id: cyber_auditing_kubernetes_cluster_rbac
name: Auditing Kubernetes Cluster RBAC
description: Audit Kubernetes RBAC: cluster-admin bindings and wildcard verbs.
risk: moderate
permissions: [k8s.read]
requires_confirmation: true
tags: [kubernetes]
version: 1.0.0
---
# Auditing Kubernetes Cluster RBAC

## Purpose

Audit Kubernetes role-based access control across a cluster — Roles, ClusterRoles,
RoleBindings, and ClusterRoleBindings — to find over-privileged subjects, anonymous access,
and bindings that hand out cluster-admin equivalent power, before they are exploited for
lateral movement or persistence.

## When to use

- Periodic Kubernetes security reviews and compliance audits.
- After incident response involving a cluster (compromised service account, escaped pod).
- When onboarding a new cluster into the security program.
- Before granting a third party or CI system access to a cluster.

See also: auditing-kubernetes-rbac-privilege-escalation.md, analyzing-kubernetes-audit-logs.md

## Prerequisites

- Written authorization and a defined scope: cluster name(s) and namespaces in bounds.
- Read-only kubeconfig access (`get`, `list` on rbac.authorization.k8s.io resources
  cluster-wide); no write access needed for the audit.
- Inventory of expected platform admins, CI/CD service accounts, and third-party
  integrations.

## Procedure

1. **Inventory all RBAC objects.**
   - Dump `kubectl get clusterroles,clusterrolebindings` and, per namespace,
     `kubectl get roles,rolebindings -A`.
   - Save the YAML (`-o yaml`) with timestamps — this is the audit's primary evidence.

2. **Find cluster-admin equivalents.**
   - List every ClusterRoleBinding referencing `cluster-admin`:
     `kubectl get clusterrolebindings -o json | jq '.items[] | select(.roleRef.name==
     "cluster-admin")'`.
   - Each subject here is a full cluster compromise waiting to happen — every one needs a
     named owner and justification.

3. **Hunt wildcard verbs and resources.**
   - Search roles for `verbs: ["*"]` or `resources: ["*"]`; a wildcard ClusterRole bound to
     a broad subject is effectively cluster-admin.
   - Pay special attention to `secrets` (credential theft), `pods/exec` (code execution),
     and `clusterroles`/`clusterrolebindings` (privilege escalation primitives).

4. **Audit service accounts.**
   - List service accounts and their bindings; flag default service accounts with
     non-default bindings and CI/CD accounts holding cluster-wide rights.
   - Check automounting: service account tokens mounted into pods that don't need API
     access expand the blast radius of any container escape.

5. **Check anonymous and unauthenticated access.**
   - Review bindings to `system:anonymous` and `system:unauthenticated`; the API server
     flags `--anonymous-auth` determine what's reachable.
   - Verify no RoleBinding grants anonymous users more than health-check endpoints.

6. **Review aggregated ClusterRoles.**
   - Inspect ClusterRoles using aggregation rules — permissions accumulate from labeled
     ClusterRoles and are easy to underestimate.
   - Resolve the effective rule set (tools like `rakkess` or `kubectl auth can-i --list
     --as=<subject>`) rather than eyeballing.

7. **Test effective permissions per subject.**
   - For each high-interest subject run
     `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa> -A` (or
     `--as=<user>`).
   - Compare effective permissions against the subject's documented need; document every
     excess grant as a finding.

8. **Correlate with the audit log.**
   - If the Kubernetes audit log is available, check whether powerful verbs (e.g.,
     `create pods/exec`, `get secrets`) are actually exercised — unused power is the
     strongest least-privilege argument.
   - Look for anomalous subjects exercising rights outside their normal pattern.

9. **Remediate and verify.**
   - Replace wildcard roles with scoped Roles, move cluster-wide bindings to namespace
     bindings where possible, and remove anonymous grants.
   - Re-run the dumps and `auth can-i` checks to confirm each finding is closed; keep the
     before/after YAML.

## Key tools & commands

- `kubectl get clusterroles,roles,clusterrolebindings,rolebindings -A -o yaml` — evidence
  collection.
- `kubectl auth can-i --list --as=<subject> [-A|--namespace=<ns>]` — effective permission
  checks; also `kubectl auth can-i <verb> <resource> --as=<subject>`.
- `rakkess` (`rakkess resource -v clusterrole -v role`) — subject-to-resource access
  matrix.
- `kubectl-who-can` plugin (`kubectl who-can get secrets`) — reverse lookup: who can do
  what.
- `rbac-lookup`, `kubeaudit`, `kubesec` — supplementary scanners; adjudicate their output
  manually.

## Expected outputs

- Complete RBAC object dumps with timestamps.
- Findings: subject, binding, effective permissions, evidence, severity
  (cluster-admin equivalents, wildcards, anonymous grants, excess service account rights).
- Effective-permission test results per high-interest subject.
- Remediation log with before/after YAML diffs.

## Pitfalls

- Aggregation rules and wildcard expansion — eyeballing ClusterRoles underestimates
  effective power; always resolve with `auth can-i --list`.
- `system:masters` group membership via client certificates bypasses RBAC entirely —
  check who holds those certificates, not just the bindings.
- Forgetting that `pods/exec` + any pod access equals node-level code execution paths in
  many configurations.
- Treating scanner output as final — confirm every finding against the live YAML and an
  `auth can-i` check.

## References

- MITRE ATT&CK: T1078 (Valid Accounts), T1609 (Container Administration Command), T1552
  (Unsecured Credentials).
- Kubernetes documentation: "Using RBAC Authorization".
- CIS Kubernetes Benchmark: RBAC-related controls.
- kubectl reference: `kubectl auth can-i`.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
