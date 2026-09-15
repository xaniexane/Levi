---
skill_id: cyber_implementing_rbac_hardening_for_kubernetes
name: Implementing RBAC Hardening for Kubernetes
description: Harden Kubernetes RBAC — least-privilege roles, no wildcard verbs, service-account scoping, and regular access reviews that keep cluster-admin rare.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, rbac, access-control, hardening]
version: 1.0.0
---
## Purpose

Make Kubernetes authorization follow least privilege: every human and workload gets exactly the verbs on exactly the resources it needs, in the narrowest namespace scope, with cluster-admin treated as the emergency-only role it should be. RBAC hardening closes the most common Kubernetes privilege-escalation paths — over-permissive bindings that turn a compromised pod or stolen kubeconfig into cluster takeover.

## When to use

- Hardening clusters to CIS Benchmark expectations for access control.
- Remediating audits that find cluster-admin bindings for developers or CI systems.
- Multi-team or multi-tenant clusters needing namespace-scoped access.
- After incidents involving compromised service accounts with excessive permissions.
- Standardizing access provisioning (SSO groups → ClusterRoles) instead of ad-hoc bindings.

## Prerequisites

- Inventory of all subjects: human users/groups (via OIDC/SSO), service accounts, and their current bindings (`kubectl` RBAC audit tooling like `rbac-lookup`, `audit2rbac`, or `k9s`).
- Defined access model: who needs what (developers, SREs, CI/CD, operators) per environment tier.
- OIDC/SSO integration for human authentication (RBAC without identity is just usernames in bindings).
- Cluster-admin break-glass procedure with monitored use.
- Test cluster for validating tightened roles before production.

## Procedure

1. **Audit current bindings.** Enumerate every ClusterRoleBinding and RoleBinding, flagging: bindings to `cluster-admin` (list every subject — the list is always longer than expected), wildcard verbs (`*`), wildcard resources, and bindings to `system:` groups or default service accounts. This audit is the baseline; repeat it quarterly.
2. **Eliminate wildcard and cluster-admin sprawl.** Replace `verbs: ["*"]` with explicit verb lists; replace `resources: ["*"]` with named resources. Remove cluster-admin from humans and CI — almost nobody needs it day-to-day. For each removed binding, provide the narrower alternative (namespaced Role, or a purpose-built ClusterRole like a read-only debug role).
3. **Scope service accounts tightly.** Every workload gets its own service account (never the `default` SA with added powers), bound with Roles limited to its namespace and the exact resources/verbs it needs. Disable automounting of service-account tokens where pods don't need API access (`automountServiceAccountToken: false`). Audit token audiences and expirations — bound, short-lived tokens over legacy long-lived ones.
4. **Bind humans via SSO groups.** Map IdP groups to Roles/ClusterRoles (e.g., `k8s-dev-team → edit in namespace team-a`, `k8s-sre → admin in namespaces, read-only cluster-wide`). Individuals get bindings only as documented exceptions. When someone changes teams, the IdP group change propagates — no stale bindings to clean.
5. **Protect the powerful verbs.** Treat `escalate`, `bind`, `impersonate`, `create` on pods/exec, `*` on secrets, and `update` on validatingwebhookconfigurations as privileged: any binding granting these gets documented justification, owner, and expiry. These verbs are the privilege-escalation primitives — `bind`/`escalate` let a holder grant themselves more power.
6. **Namespace-scope by default.** Prefer Roles/RoleBindings over ClusterRoles/ClusterRoleBindings; when cluster-scoped access is genuinely needed (CRDs, nodes, namespaces), create minimal ClusterRoles (e.g., read-only nodes for monitoring) rather than reusing `admin`/`edit`/`view` defaults with extra grants.
7. **Enforce with policy and CI.** Add Gatekeeper/Kyverno or CI checks blocking new wildcard bindings and cluster-admin grants without approved exception labels. RBAC hardening decays without prevention — every "temporary" cluster-admin becomes permanent.
8. **Review on cadence and monitor in audit logs.** Quarterly RBAC reviews with team leads; alert on: new cluster-admin bindings, bindings granting `escalate`/`bind`/`impersonate`, service-account token requests outside norms, and use of powerful verbs by unusual subjects. Kubernetes audit logs are the detective control for RBAC — ship and monitor them.

## Expected outputs

- RBAC audit baseline with cluster-admin and wildcard findings remediated.
- Per-team/per-workload least-privilege Roles with SSO-group bindings.
- Scoped service accounts with token automount disabled where unneeded.
- Privileged-verb register with justifications and expiries.
- Policy/CI prevention of new excessive bindings; audit-log monitoring.

## Pitfalls

- **Default service account with powers.** The `default` SA in a namespace accumulating bindings is a shared privileged identity for every unconfigured pod. Give workloads their own SAs.
- **CI with cluster-admin.** Build pipelines deploying with cluster-admin turn every code change into potential cluster takeover. Scope CI service accounts to their namespaces and verbs.
- **Forgetting `bind` and `escalate`.** Teams remove `*` but leave these verbs, preserving self-escalation. They belong in the privileged-verb register with the strictest scrutiny.
- **Long-lived tokens in secrets.** Legacy service-account token secrets persist indefinitely and get copied into CI systems. Migrate to bound projected tokens with short lifetimes.
- **Audit logs not shipped.** RBAC hardening without audit-log monitoring means you'll never know when someone grants themselves cluster-admin at 3 a.m. Ship the logs, alert on the grants.

## References

- Kubernetes RBAC documentation — https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- Kubernetes audit logging — https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/
- CIS Kubernetes Benchmark — https://www.cisecurity.org/cis-benchmarks
- MITRE ATT&CK T1078 (Valid Accounts — service account abuse) — https://attack.mitre.org/techniques/T1078/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
