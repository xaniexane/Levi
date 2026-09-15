---
skill_id: cyber_securing_github_actions_workflows
name: Securing GitHub Actions Workflows
description: Harden GitHub Actions: OIDC to cloud, pinned actions, minimal token permissions, and protected environments.
risk: info
permissions: []
requires_confirmation: false
tags: [cicd, github, supply-chain]
version: 1.0.0
---
## Purpose
GitHub Actions workflows are privileged automation with access to code, secrets, and cloud environments, making them a prime supply-chain target. This playbook hardens them: least-privilege tokens, pinned third-party actions, OIDC instead of long-lived cloud credentials, and environment protection rules for deployments.

## When to use
- Security review of existing Actions workflows.
- New repository or organization Actions standards.
- After a supply-chain incident involving CI/CD.
- Compliance requiring controlled deployment pipelines.

## Prerequisites
- Organization/repo admin access to Actions settings.
- Inventory of workflows, third-party actions, and secrets in use.
- Cloud IAM configured for OIDC federation (if deploying to cloud).
- Branch protection and environment policies understood.

## Procedure
1. Set organization defaults: `GITHUB_TOKEN` permissions to read-only; workflows escalate explicitly where needed.
2. Pin all third-party actions to full commit SHAs, not mutable tags; review updates via Dependabot for Actions.
3. Replace long-lived cloud credentials with OIDC federation; scope the IAM role's trust to specific repos and refs.
4. Require environments with protection rules (required reviewers, wait timers, branch restrictions) for production deployments.
5. Audit `pull_request_target` and other dangerous triggers; ensure untrusted code cannot access secrets.
6. Enable secret scanning and push protection on repositories to catch leaked credentials.
7. Restrict which actions can run (allowlist verified creators or specific SHAs) at the organization level.
8. Log workflow runs centrally; alert on workflow file changes, new secrets access, and self-hosted runner anomalies.
9. Audit reusable workflows and composite actions with the same rigor as third-party actions.
10. Validate workflow_dispatch inputs before use in scripts; they are attacker-controlled.
11. Monitor the audit log for workflow file changes outside of normal pull requests.

## Expected outputs
- Hardened workflow templates and organization Actions policies.
- OIDC federation configuration replacing stored cloud credentials.
- Monitoring rules for workflow and runner anomalies.
- Reusable workflow and composite action audit results.
- Input-validation patterns for workflow_dispatch.
- Workflow-change monitoring alerts.

## Pitfalls
- Pinning to tags is not pinning; tags move, SHAs do not.
- `pull_request_target` with checkout of the PR is a classic secret-exfiltration vector.
- Self-hosted runners persist state between jobs; treat them as sensitive infrastructure.
- Overly broad OIDC trust (any branch) lets feature branches assume production roles.
- Workflow dispatch inputs are attacker-controlled; validate before use in scripts.
- Reusable workflows inherit the caller's permissions; review the combination, not just the callee.
- Fork pull requests can exfiltrate secrets through crafted workflows; keep the default restrictions.
- Environment protection rules are bypassed by direct pushes to deployment branches; protect the branches too.

## References
- GitHub Docs: Security hardening for GitHub Actions.
- GitHub Docs: OpenID Connect with cloud providers.
- NIST SP 800-204D (draft) / SSDF (SP 800-218) for secure software development.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
