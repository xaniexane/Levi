# Analyzing Kubernetes Audit Logs

## Purpose

The Kubernetes API server audit log records who did what to which resource —
every `kubectl exec`, secret read, role binding change, and anonymous request.
This playbook shows how to enable useful auditing, query the logs, and
recognize the patterns of cluster compromise: credential theft, privilege
escalation via RBAC, and malicious workloads.

## When to use

- Investigating a suspected cluster compromise or leaked service-account token.
- Auditing privileged actions: `exec` into pods, secret/configmap reads,
  cluster-role bindings.
- Compliance review of administrative access to the cluster.
- Tuning detection rules for a Kubernetes threat-detection pipeline (Falco, SIEM).

See also: auditing-kubernetes-cluster-rbac.md

## Prerequisites

- Written authorization covering the cluster(s); audit logs can contain
  secrets in request/response payloads — treat them as sensitive.
- Cluster-admin or log-access rights; know where your audit backend writes
  (file on control plane, webhook, or log aggregator).
- An audit policy that actually records what you need (see step 1) — the
  default in many distros logs almost nothing.

## Procedure

1. Verify the audit policy on the API server (`--audit-policy-file` in
   `/etc/kubernetes/manifests/kube-apiserver.yaml` or your managed-service
   equivalent). Ensure rules log at least `RequestResponse` for `secrets`,
   `clusterroles`, `clusterrolebindings`, `rolebindings`, and `pods/exec`.
   Stages to capture: `RequestReceived`, `ResponseStarted`, `ResponseComplete`.
2. Locate the logs: `--audit-log-path` on the control plane, or your
   webhook/SIEM destination. Confirm log completeness for the incident window.
3. Establish the baseline: which service accounts normally talk to the API,
   from which source IPs, and which users run `kubectl` interactively.
   Service accounts have stable, boring patterns — deviations are signal.
4. Hunt for the high-value verbs and resources with `jq`:
   - `pods/exec` and `pods/attach`: `.verb=="create" and .objectRef.subresource=="exec"`
   - Secret reads: `.objectRef.resource=="secrets" and .verb=="get"`
   - RBAC changes: `clusterrolebindings`/`rolebindings` create/update.
   - Anonymous or unauthenticated requests: `.user.username=="system:anonymous"`.
5. Investigate suspicious service-account usage: a token used from an external
   IP, a normally-quiet SA suddenly listing secrets cluster-wide, or
   `system:serviceaccount:kube-system:default`-adjacent anomalies.
6. Correlate with workload events: new privileged pods, hostPath mounts, or
   `hostNetwork: true` appearing near the suspicious API activity
   (`kubectl get events --all-namespaces`, admission-controller logs).
7. Check for persistence via the API: new service accounts, added
   cluster-role bindings, or mutating webhooks registered by the attacker.
8. Scope the blast radius: list every secret the compromised identity read
   (they are all burned — rotate them), and every namespace it touched.
9. Preserve evidence: export the relevant audit-log slice with hashes, and
   record the audit policy in effect at the time (a policy gap is itself a
   finding to remediate).

## Key tools & commands

- `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>` —
  what a suspected service account can do.
- `jq` filters over audit JSON, e.g.:
  `jq 'select(.verb=="create" and .objectRef.subresource=="exec")' audit.log`
- `kubectl get clusterrolebindings,rolebindings --all-namespaces -o wide` —
  RBAC snapshot for comparison.
- Falco with k8s-audit rules — real-time detection on the audit stream.
- `stern` / aggregated logging (Loki, Elasticsearch) — searching across
  control-plane log volume.
- `kube-apiserver` manifest flags: `--audit-log-path`,
  `--audit-log-maxage`, `--audit-policy-file`.

## Expected outputs

- Timeline of attacker API activity: identities, source IPs, resources touched.
- List of compromised credentials and secrets requiring rotation.
- RBAC/persistence artifacts created (bindings, accounts, webhooks).
- Detection rules or Falco additions covering the observed techniques.
- Remediation: tightened audit policy, least-privilege RBAC fixes.

## Pitfalls

- Auditing at `Metadata` level only: you see that a secret was read but not
  which one — use `Request`/`RequestResponse` for sensitive resources, and
  accept the volume.
- Audit logs omit `watch` response bodies by design; long-running watches can
  hide exfiltration — pair with network telemetry.
- Managed clusters (EKS/GKE/AKS) expose audit logs differently (CloudTrail /
  Cloud Audit Logs / diagnostic settings); the API-server file path may not
  exist — check your provider's docs.
- Request bodies can contain secrets; redact before pasting into tickets.
- Clock skew between control-plane nodes scrambles timelines — verify NTP.

## References

- Kubernetes docs: "Auditing" (kubernetes.io/docs/tasks/debug/debug-cluster/audit)
- MITRE ATT&CK: T1078 (Valid Accounts), T1552 (Unsecured Credentials),
  T1609 (Container Administration Command)
- Falco k8s-audit rules documentation (falco.org)
- CIS Kubernetes Benchmark (audit-logging controls)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
