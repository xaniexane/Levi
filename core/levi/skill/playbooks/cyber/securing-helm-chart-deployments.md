---
skill_id: cyber_securing_helm_chart_deployments
name: Securing Helm Chart Deployments
description: Secure Helm usage: values hygiene, chart provenance, linting, and policy enforcement on rendered manifests.
risk: info
permissions: []
requires_confirmation: false
tags: [kubernetes, helm, supply-chain]
version: 1.0.0
---
## Purpose
Helm charts package Kubernetes deployments but also package risk: insecure defaults, secrets in values, and untrusted chart sources. This playbook secures the Helm workflow end to end: trusted chart sources with provenance, safe values management, linting and scanning of rendered output, and admission policy as the final gate.

## When to use
- Standardizing Helm usage across teams.
- Security review before adopting third-party charts.
- After an incident caused by chart defaults (e.g. privileged pods).
- Building a platform golden-path for Kubernetes deployments.

## Prerequisites
- Helm v3+ installed; inventory of charts and values files in use.
- OCI registry or chart repository with authentication.
- External secret management (External Secrets Operator or equivalent).
- Policy engine (Kyverno/OPA) for admission-time enforcement.

## Procedure
1. Source charts only from trusted repositories; prefer OCI registries with authentication over public HTTP repos.
2. Verify chart provenance and signatures where provided before first use.
3. Never store secrets in values files; use secret references resolved at deploy time from a secrets manager.
4. Lint every chart (`helm lint`) and template-review rendered output before install.
5. Scan rendered manifests with Kubesec/Trivy config scanning in CI; fail on critical findings.
6. Override insecure chart defaults in your values: non-root users, dropped capabilities, read-only filesystems, resource limits.
7. Pin chart versions; use lock files or digests so deployments are reproducible.
8. Enforce admission policies (Pod Security Standards via Kyverno/OPA) so insecure renders cannot deploy even if CI is bypassed.
9. Use `helm template --validate` against a test cluster to catch schema errors before CI scanning.
10. Review Helm hooks for elevated privileges; hooks run outside the normal lifecycle.
11. Verify that chart dependencies are also pinned and scanned, not just the parent chart.

## Expected outputs
- Approved chart catalog with versions and provenance records.
- Secure values baselines per chart with documented overrides.
- CI scanning and admission policy configuration.
- Template validation results per chart version.
- Helm hook privilege review.
- Dependency pinning and scan evidence.

## Pitfalls
- Third-party chart defaults prioritize convenience over security; always review values.
- `--set` on the command line leaks secrets into shell history and CI logs.
- Subcharts inherit silently; audit dependencies, not just the top chart.
- Helm releases store values in cluster secrets; restrict access to release secrets.
- Helm hooks run with elevated timing; review hook resources for privilege.
- Post-upgrade hooks can leave orphaned resources; audit after upgrades.
- `helm uninstall` may leave CRDs behind; plan CRD lifecycle explicitly.
- Values files committed to git often contain secrets; scan repositories historically, not just going forward.

## References
- Helm official documentation: provenance and best practices.
- Kubernetes documentation: Pod Security Standards.
- NIST SP 800-190, Application Container Security Guide.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
