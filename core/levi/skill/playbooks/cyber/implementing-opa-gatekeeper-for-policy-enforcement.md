---
skill_id: cyber_implementing_opa_gatekeeper_for_policy_enforcement
name: Implementing OPA Gatekeeper for Policy Enforcement
description: Enforce Kubernetes admission policies with OPA Gatekeeper — constraint templates, staged dry-run rollout, and exception management.
risk: low
permissions: []
requires_confirmation: false
tags: [kubernetes, policy-as-code, admission-control, opa]
version: 1.0.0
---
## Purpose

Make cluster policy executable: OPA Gatekeeper admits or denies Kubernetes objects based on Rego policies packaged as ConstraintTemplates and Constraints. Required labels, image registries, resource limits, forbidden capabilities — instead of wiki pages nobody reads, violations are rejected at the API server with an explanation, before the non-compliant workload ever runs.

## When to use

- Enforcing organizational Kubernetes standards (allowed registries, required labels/annotations, resource quotas) automatically.
- Complementing Pod Security Standards with custom rules PSS doesn't cover (image provenance, network policy presence, trusted registries).
- Meeting compliance requirements for preventive technical controls in clusters.
- Multi-cluster or multi-tenant environments needing consistent policy from a central library.
- Shifting policy left: the same Rego policies can validate manifests in CI via conftest.

## Prerequisites

- Gatekeeper installed on the cluster (or a plan to use its audit-only mode first) with webhook HA configured.
- Inventory of the policies to enforce, prioritized — start with 5–10 high-value rules, not fifty.
- Rego competence on the team or a curated constraint library to start from (Gatekeeper's example library covers the common cases).
- Exemption process defined: who approves, how long exemptions last, where they're recorded.
- CI integration point (conftest) so developers see violations before the cluster rejects them.

## Procedure

1. **Start in audit mode.** Deploy Gatekeeper with constraints set to `enforcementAction: dryrun`. The audit feature reports violations across existing resources without blocking anything. Run for a full release cycle and triage every violation class: fixable in manifests, legitimate exception, or bad rule.
2. **Build the constraint library from the audit.** Write ConstraintTemplates in Rego for the validated rules — required labels, allowed image registries (deny-by-default on registry), resource requests/limits required, disallowed hostPath/hostNetwork, required network policy presence. Keep each template focused on one concern; monolithic templates become unmaintainable.
3. **Test constraints like code.** Unit-test Rego with `opa test` using admission-review fixtures covering allow, deny, and edge cases. A buggy constraint that denies legitimate deploys cluster-wide is an outage authored in policy language — test it as rigorously as application code.
4. **Enforce incrementally.** Flip constraints to `deny` one at a time, least-disruptive first (e.g., required labels before registry restrictions). Announce each enforcement with examples of compliant manifests and a grace period. Monitor denial rates after each flip; a spike means the rule or the communication needs work.
5. **Manage exemptions explicitly.** Use namespace-scoped exemptions or exemption parameters with owner, justification, and expiry — never permanent silent bypasses. Audit exemptions quarterly; the exemption list is where policy goes to die if unmanaged.
6. **Shift left with conftest.** Run the same Rego policies against manifests in CI (`conftest test`) so developers get feedback in the pull request, not at deploy time. Admission denial should be the safety net, not the first notification.
7. **Handle the bypass paths.** Gatekeeper sees what passes through the API server: restrict who can modify Gatekeeper's own resources and who holds cluster-admin (they bypass webhooks), and ensure emergency break-glass procedures are documented and alerted rather than quietly used.
8. **Sync and version the library.** Store all templates and constraints in git, sync to clusters via GitOps (Argo CD/Flux), and version the library so clusters can pin releases. Policy changes get the same review, testing, and rollout discipline as application changes.

## Expected outputs

- Gatekeeper deployed with audited-then-enforced constraint library in version control.
- Rego unit tests covering allow/deny/edge cases per template.
- Exemption register with owners and expiries.
- CI (conftest) integration giving pre-deploy feedback.
- Denial monitoring feeding the SIEM; GitOps-managed policy rollout.

## Pitfalls

- **Enforcing on day one.** Flipping fifty constraints to deny simultaneously blocks legitimate deploys and gets Gatekeeper uninstalled. Audit → triage → enforce incrementally.
- **Rego without tests.** Untested Rego is a production outage waiting for an unusual but legitimate manifest. Test every template.
- **Exemptions without expiry.** Permanent exemptions accumulate until the policy is decorative. Time-box everything.
- **Ignoring webhook availability.** If the Gatekeeper webhook is down and `failurePolicy` is Fail, the API server blocks all writes — an availability risk. Run HA webhooks and choose failurePolicy deliberately per constraint criticality.
- **Policy that developers can't satisfy.** A rule requiring labels that no tooling sets, or registries the pipeline can't push to, just generates resentment and exemption requests. Pair each enforced rule with the paved path to compliance.

## References

- OPA Gatekeeper documentation — https://open-policy-agent.github.io/gatekeeper/website/docs/
- Open Policy Agent documentation — https://www.openpolicyagent.org/docs/
- Kubernetes dynamic admission control concepts — https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
- CIS Kubernetes Benchmark — https://www.cisecurity.org/cis-benchmarks
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
