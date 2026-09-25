---
skill_id: cyber_securing_container_registry_with_harbor
name: Securing Container Registries with Harbor
description: Harden Harbor registries: RBAC, robot accounts, vulnerability scanning, image signing, and replication security.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, harbor, registry]
version: 1.0.0
---
## Purpose
Harbor is a widely deployed open-source registry with built-in security features that are often left at defaults. This playbook configures them properly: project-scoped RBAC, robot accounts for CI, integrated scanning, Cosign signing, and secure replication between Harbor instances.

## When to use
- Deploying or hardening a Harbor registry instance.
- Security review of an existing Harbor deployment.
- Multi-site replication design requiring trusted image flow.
- Compliance requiring scanned and signed images.

## Prerequisites
- Harbor admin access and the deployment topology (standalone or replicated).
- OIDC/LDAP identity source for centralized authentication.
- Scanner (Trivy/Clair) deployment for Harbor integration.
- Backup strategy for Harbor's database and storage.

## Procedure
1. Integrate OIDC/LDAP so Harbor identities are centrally managed; disable local admin except break-glass.
2. Organize repositories into projects with least-privilege RBAC; avoid system-wide admin roles.
3. Create robot accounts per CI pipeline with push-only or pull-only scope and rotation schedules.
4. Enable vulnerability scanning on push and on a schedule; set CVE allowlists per project with expiry.
5. Enable Cosign signing and configure immutable tags on production projects.
6. Configure replication rules with TLS and authentication; verify image integrity across sites.
7. Turn on audit logging and ship Harbor logs to the SIEM; alert on permission changes and anomalous pulls.
8. Harden the Harbor deployment itself: TLS everywhere, secrets in a manager, patched components, restricted admin network access.
9. Enable Harbor's immutable tag rules on release repositories to prevent tag-overwrite attacks.
10. Restrict Harbor jobservice log access; logs can contain credentials.
11. Test Harbor backup and restore; the database holds robot tokens and project configuration.

## Expected outputs
- Harbor security configuration record (auth, RBAC, robot accounts).
- Scanning, signing, and immutability policy per project.
- Log pipeline and alerting for registry activity.
- Immutable tag rule configuration per release project.
- Log access control review results.
- Harbor backup/restore test evidence.

## Pitfalls
- Robot account tokens in CI logs leak; use masked variables and short expiry.
- CVE allowlists without expiry become permanent; review them on a cadence.
- Replication without verification can propagate tampered images; verify signatures at each hop.
- Harbor's own database holds credentials and tokens; back it up encrypted and restrict access.
- Harbor jobservice logs can contain credentials; restrict log access.
- Replication credentials with broad scope become lateral-movement material; scope them tightly.
- Upgrading Harbor without testing can break OIDC; validate auth after every upgrade.
- Project quotas prevent registry DoS via image spam; enable them per project.

## References
- Harbor official documentation (goharbor.io/docs).
- NIST SP 800-190, Application Container Security Guide.
- CIS Harbor Benchmark (where available).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
