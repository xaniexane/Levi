---
skill_id: cyber_implementing_secrets_management_with_vault
name: Implementing Secrets Management with Vault
description: Deploy HashiCorp Vault for centralized secrets management — dynamic secrets, rotation, access policies, and safe application integration patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [secrets, vault, key-management, devsecops]
version: 1.0.0
---
## Purpose

End static, long-lived, scattered secrets. HashiCorp Vault centralizes secret storage with encryption, fine-grained access policies, full audit logging, and — its killer feature — dynamic secrets: credentials generated on demand with short TTLs that Vault revokes automatically. Applications stop storing passwords; they request them, use them, and watch them expire.

## When to use

- Replacing secrets in config files, environment variables, and code with managed retrieval.
- Meeting rotation and audit requirements (PCI DSS 4.0, SOC 2) for credentials at scale.
- Providing database, cloud, and PKI credentials to applications and CI/CD without human handling.
- Implementing short-lived credentials that shrink the theft window from months to minutes.
- Centralizing the dozen ad-hoc secret stores (wikis, shared drives, chat) into one audited system.

## Prerequisites

- Vault cluster architecture: HA (Raft integrated storage) across failure domains, with DR replication for critical deployments.
- Initialization and unseal ceremony: Shamir shares or auto-unseal via cloud KMS, with share holders documented and tested.
- Authentication methods planned: which identities use Vault (AppRole for machines, OIDC/JWT for CI and humans, Kubernetes auth for pods).
- Policy model designed: least-privilege paths per application/team before onboarding begins.
- Backup and disaster-recovery procedures for Vault's own storage (Raft snapshots, tested restores).

## Procedure

1. **Deploy HA Vault and perform the ceremony properly.** Initialize with Shamir's Secret Sharing distributed among named key holders (or auto-unseal with KMS plus a documented break-glass), enable audit devices from day one (audit logs are the compliance value of Vault — without them it's an encrypted key-value store), and configure TLS everywhere. Test unseal and DR failover before onboarding any secret.
2. **Design the policy and namespace model.** Structure secret paths by team/application/environment (`secret/apps/payments/prod/...`), write policies granting least privilege per path, and use namespaces or mount separation for strong multi-tenancy. Every policy gets an owner; review policies quarterly — Vault policies accumulate like firewall rules.
3. **Onboard static secrets first (KV).** Migrate existing static secrets into KV v2 with versioning: one secret per path, no secret sharing between applications (shared secrets can't be rotated per-consumer), and metadata noting owner and rotation schedule. Delete the secrets from their old locations (config files, wikis) — migration without cleanup doubles the exposure.
4. **Deploy dynamic secrets where they shine.** Configure database secret engines (Vault generates short-lived DB credentials per request), cloud engines (AWS/GCP/Azure STS credentials with minutes-long TTLs), and SSH (one-time or short-lived signed keys). Dynamic secrets eliminate rotation as a separate problem — expiry is built in. Prioritize the highest-risk static credentials first.
5. **Integrate applications safely.** Preferred patterns in order: Vault Agent with template rendering or API (workload authenticates via AppRole/K8s auth, never with a long-lived token baked into the image), secrets injected at deploy time for legacy apps, and CI/CD via JWT/OIDC auth (GitHub Actions, GitLab) with per-workflow policies. Never: tokens in code, root tokens anywhere except the sealed envelope, or shared tokens across applications.
6. **Automate rotation for what remains static.** For secrets that can't be dynamic (third-party API keys), use Vault's rotation capabilities or scheduled automation, with applications re-reading on rotation (Vault Agent handles reload). Track rotation compliance per secret — a static secret with a rotation policy nobody enforces is the old problem with new tooling.
7. **Monitor and audit relentlessly.** Ship audit logs to the SIEM and alert on: root token use (should be never outside emergencies), policy changes, secret reads outside normal patterns, and authentication failures. The audit log is also the forensic record — protect it with the same care as the secrets.
8. **Plan for Vault's own failure.** Maintain tested Raft snapshot restores, documented seal/unseal procedures with available key holders (including off-hours), and a break-glass process for Vault-down scenarios (cached secrets with defined staleness tolerance). Vault is critical infrastructure — treat an outage with incident-response seriousness.

## Expected outputs

- HA Vault cluster with documented init/unseal ceremony and DR tested.
- Policy/namespace model with least-privilege paths and quarterly reviews.
- Migrated static secrets with old locations cleaned; dynamic secrets for databases/cloud/SSH.
- Application integration via Agent/AppRole/K8s/JWT patterns (no baked-in tokens).
- Audit logging to SIEM with alerting; backup/restore and break-glass procedures.

## Pitfalls

- **Root token in daily use.** The root token should be revoked after initial setup (or sealed away). Operational use of root voids the entire access model — and it's more common than anyone admits.
- **Long-lived tokens in applications.** A Vault token baked into a container image is just a password with extra steps. Use short-lived, auto-renewing workload auth (AppRole with secret-id rotation, K8s auth, JWT).
- **Migration without cleanup.** Secrets copied into Vault but left in the old config files, wikis, and git history means the old exposures persist. Migration includes deletion.
- **No audit device.** Vault without audit logging loses non-repudiation — you can't prove who accessed what. Enable audit devices before onboarding the first secret.
- **Single point of failure thinking.** Vault down means applications can't get secrets. Design for HA, cache appropriately, and rehearse the outage — the secrets manager failing closed shouldn't fail the business.

## References

- HashiCorp Vault documentation — https://developer.hashicorp.com/vault/docs
- NIST SP 800-57 Part 1 Rev. 5 (key management) — https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final
- MITRE ATT&CK T1552 (Unsecured Credentials), T1555 (Credentials from Password Stores) — https://attack.mitre.org/
- PCI DSS v4.0 Requirements 3.6–3.7, 8.3 (key and credential management) — https://www.pcisecuritystandards.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
