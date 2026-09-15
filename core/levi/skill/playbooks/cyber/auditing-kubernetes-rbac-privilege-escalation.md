# Auditing Kubernetes RBAC for Privilege Escalation Paths

## Purpose

Go beyond a static RBAC inventory to find *paths* — chains of permissions that let a
low-privilege subject reach cluster-admin-equivalent power step by step (e.g., create pods
→ mount a privileged service account token → escalate). This playbook models the attack
graph and validates each hop.

## When to use

- After the baseline RBAC inventory (see the companion cluster RBAC playbook) shows
  complex or layered bindings.
- During penetration tests or red-team-adjacent assessments of a cluster (authorized,
  defensive scope).
- After incident response where lateral movement inside the cluster is suspected.
- When a new operator, admission controller, or CI integration adds RBAC surface.

See also: auditing-kubernetes-cluster-rbac.md

## Prerequisites

- Written authorization and a defined scope: cluster(s) and namespaces in bounds, and
  whether *active validation* (actually exercising a hop in a sandbox namespace) is
  permitted — default to read-only modeling unless validation is explicitly approved.
- Read-only kubeconfig access cluster-wide, plus the RBAC dumps from the companion audit.
- A sandbox namespace for any approved active validation, with cleanup afterwards.

## Procedure

1. **Build the permission graph.**
   - From the RBAC dumps, model subjects → (verbs, resources) → objects for every
     binding, including aggregated ClusterRoles resolved to their effective rules.
   - Include non-RBAC edges: which service account tokens are mounted into which pods
     (`kubectl get pods -A -o jsonpath` over `spec.serviceAccountName` and volume mounts).

2. **Enumerate known escalation primitives.**
   - For each subject, check for these high-value rights: `create`/`update`/`patch` on
     `pods`, `deployments`, `daemonsets`; `create` on `pods/exec` and `pods/attach`;
     `get`/`list` on `secrets`; `create`/`update` on `roles`, `clusterroles`,
     `rolebindings`, `clusterrolebindings`; `escalate`/`bind` verbs; `impersonate` on
     `users`/`groups`/`serviceaccounts`.

3. **Trace pod-creation → service-account-token paths.**
   - A subject that can create pods in a namespace can mount *any* service account token
     in that namespace — check which powerful service accounts exist per namespace
     (step 1's token map) and whether the subject's pod-creation right reaches them.
   - Flag namespaces where a low-privilege deployer coexists with a privileged service
     account.

4. **Trace secret-access paths.**
   - `get secrets` in `kube-system` (or any namespace holding powerful SA tokens or cloud
     credentials) is a direct hop to those identities' full permissions.
   - Map which secrets each readable namespace exposes and what power those credentials
     confer.

5. **Trace role-granting paths.**
   - Subjects with `bind`/`escalate` or write access to rolebindings can grant themselves
     (or a controlled account) any role they can reference — including cluster-admin.
   - Check `kubectl auth can-i bind clusterroles --as=<subject>` style checks for each
     candidate.

6. **Check impersonation and token-request edges.**
   - `impersonate` on users/groups/serviceaccounts lets a subject become a more powerful
     identity directly.
   - The TokenRequest API (`create` on `serviceaccounts/token`) mints fresh tokens for
     powerful service accounts without touching stored secrets.

7. **Validate the top paths (if authorized).**
   - In the sandbox namespace only, exercise the highest-risk chain hop by hop (e.g.,
     create a pod mounting the target SA, then `auth can-i --list` as that SA).
   - Stop at proof of the *permission*, not at cluster takeover; record each hop's
     command and output, then delete all test artifacts.

8. **Rank paths by starting privilege and hop count.**
   - A two-hop path from an unauthenticated-adjacent subject outranks a five-hop path
     from an existing admin.
   - For each path record: entry subject, each hop (permission exercised), terminal
     privilege reached, and evidence.

9. **Remediate structurally.**
   - Break the cheapest hop: split privileged service accounts into dedicated namespaces
     with no low-privilege pod creators, remove `bind`/`escalate`, scope secret access,
     and disable token automounting where unneeded
     (`automountServiceAccountToken: false`).
   - Re-run the graph analysis to confirm no equivalent path replaced the closed one —
     escalation paths reroute around naive fixes.

## Key tools & commands

- `kubectl auth can-i --list --as=<subject> -A` — resolve effective permissions per hop.
- `kubectl get pods -A -o json` parsed for `serviceAccountName` — the token-mount map.
- `rakkess`, `kubectl-who-can` — enumerate who holds each escalation primitive.
- `kdigger` (read-only container/CI-friendly) — highlights common escalation paths from
  inside a pod context during approved validation.
- Custom graph scripts (Python + `kubernetes` client) for multi-hop path enumeration at
  scale — keep them read-only.

## Expected outputs

- Permission graph (subjects × effective rights × token-mount edges).
- Ranked privilege-escalation paths with hop-by-hop evidence.
- Validation log for authorized active checks, with cleanup confirmation.
- Remediation plan that breaks paths structurally, with re-verification results.

## Pitfalls

- Validating escalation paths in production namespaces — always use the sandbox namespace
  and clean up; a "test" pod mounting a prod SA token is itself an incident.
- Missing non-RBAC edges: cloud IAM roles for service accounts (GKE Workload Identity,
  EKS IRSA) extend the graph beyond Kubernetes RBAC.
- Closing one hop while an equivalent path remains (e.g., blocking pod creation but
  leaving `pods/exec` on an existing privileged pod).
- Treating `bind`/`escalate` as obscure — they are the most direct self-grant primitives
  and are frequently over-granted to CI accounts.

## References

- MITRE ATT&CK: T1078 (Valid Accounts), T1609 (Container Administration Command), T1552
  (Unsecured Credentials).
- Kubernetes documentation: "Using RBAC Authorization".
- CIS Kubernetes Benchmark: RBAC and pod security controls.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
