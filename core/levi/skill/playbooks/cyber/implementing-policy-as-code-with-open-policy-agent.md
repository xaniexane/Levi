---
skill_id: cyber_implementing_policy_as_code_with_open_policy_agent
name: Implementing Policy as Code with Open Policy Agent
description: Adopt Open Policy Agent for policy-as-code — Rego policy development, testing, deployment patterns, and decision-log auditing across the stack.
risk: info
permissions: []
requires_confirmation: false
tags: [policy-as-code, opa, governance, devsecops]
version: 1.0.0
---
## Purpose

Unify policy enforcement across the organization with Open Policy Agent: one policy language (Rego), one testing approach, and multiple enforcement points (Kubernetes admission, CI pipelines, API authorization, Terraform plans). Policy-as-code turns tribal-knowledge rules into versioned, tested, automatically enforced decisions — with decision logs providing the audit trail.

## When to use

- Standardizing policy enforcement across Kubernetes, CI/CD, cloud, and APIs instead of per-tool rule dialects.
- Implementing guardrails developers can test locally before enforcement blocks them.
- Meeting requirements for preventive, auditable technical controls.
- Building a platform team offering "policy as a service" to product teams.
- Replacing spreadsheet-based compliance checks with executable policy.

## Prerequisites

- Inventory of policies to codify, prioritized by value (start with 5–10, not fifty).
- Chosen enforcement points: Gatekeeper (K8s admission), conftest (CI), OPA sidecar/standalone (API authz), terraform plan evaluation.
- Rego competence on the platform team and a policy library repository with CI.
- Decision-log pipeline: where OPA decision logs go and who reviews them.
- Versioning and distribution strategy for policy bundles.

## Procedure

1. **Stand up the policy repository.** Create a git repository for Rego policies with directory structure per domain (`kubernetes/`, `terraform/`, `api/`). Every policy gets metadata: owner, description, severity, and remediation guidance shown to violators. Policies without remediation guidance generate support tickets, not compliance.
2. **Write policies test-first.** Develop each policy with `opa test` unit tests covering allow, deny, and edge cases before deployment. Structure policies for clarity: small, named rules with comments explaining the intent in business terms, not just Rego mechanics. A policy nobody can read is a policy nobody will maintain.
3. **Start with CI enforcement (conftest).** Run policies against Kubernetes manifests, Terraform plans, Dockerfiles, and CI configs in pull requests:
   ```bash
   conftest test -p policy/ deployment.yaml
   conftest test -p policy/ tfplan.json
   ```
   CI feedback is the friendliest enforcement point — developers fix issues in their workflow, not after a deploy rejection.
4. **Extend to admission control.** Deploy the same Kubernetes policies via Gatekeeper (or OPA's kube-mgmt) so the cluster enforces what CI checks. CI is advisory-speed; admission is the guarantee. Keep both in sync from the same policy bundle — drift between them confuses everyone.
5. **Add API authorization where valuable.** For services needing fine-grained authorization, integrate OPA as a sidecar or service: the application sends `{subject, action, resource, context}` and enforces the allow/deny decision. Externalize data the policy needs (user roles, resource ownership) via bundle data or the data API, with freshness SLAs.
6. **Distribute via bundles with versioning.** Package policies as versioned bundles served from a bundle server or OCI registry; consumers pin versions and upgrade deliberately. Unversioned policy distribution means a policy edit can break every consumer simultaneously with no rollback path.
7. **Enable and monitor decision logs.** Ship OPA decision logs to the SIEM/log platform: which policy decided what, for which input, with what result. Alert on deny spikes (broken policy or attack probing) and on policy-evaluation errors (a policy that errors may fail open depending on integration — verify fail-closed behavior per enforcement point).
8. **Govern the policy lifecycle.** Changes go through pull request review with tests; staged rollout (audit/warn before deny) for impactful policies; exemption mechanisms with expiry; quarterly review of the policy set for relevance and false-positive rates. Measure policy coverage (% of deployments evaluated) and violation remediation time.

## Expected outputs

- Versioned Rego policy library with tests and remediation guidance.
- CI enforcement (conftest) across IaC and manifests.
- Admission enforcement synced from the same bundles.
- API authorization integrations where applicable, with data-freshness SLAs.
- Decision-log pipeline with alerting; policy lifecycle governance.

## Pitfalls

- **Untested Rego in production.** Rego's logic-programming model surprises imperative programmers; untested policies deny legitimate traffic in subtle ways. Test everything.
- **Fail-open integrations.** Some OPA integrations default to allowing when the policy service is unreachable or errors. Verify fail-closed behavior for every enforcement point — a policy that fails open is a suggestion.
- **Policy/CI/admission drift.** The same rule enforced differently in CI vs. admission erodes trust. Single source (bundles), multiple consumers.
- **Writing policies developers can't satisfy.** Every deny needs a documented paved path to compliance, or the policy generates exemptions instead of security.
- **Performance blindness.** Complex Rego over large inputs adds latency to admission and API paths. Benchmark policy evaluation time and set budgets; optimize with indexing (rule indexing, early exits) where needed.

## References

- Open Policy Agent documentation — https://www.openpolicyagent.org/docs/
- OPA Gatekeeper documentation — https://open-policy-agent.github.io/gatekeeper/website/docs/
- Conftest documentation — https://www.conftest.dev/
- NIST SP 800-53 Rev. 5, CM-14 (Signed Components) / policy-related controls context — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
