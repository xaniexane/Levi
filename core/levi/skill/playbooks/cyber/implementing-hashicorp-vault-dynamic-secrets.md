---
skill_id: cyber_implementing_hashicorp_vault_dynamic_secrets
name: Dynamic Secrets with HashiCorp Vault
description: Implement HashiCorp Vault dynamic secrets: short-lived, auto-rotated credentials for humans and workloads.
risk: low
permissions: []
requires_confirmation: false
tags: [secrets, devops]
version: 1.0.0
---
## Purpose
Static credentials — long-lived passwords and keys sitting in config files — are stolen, leaked, and
forgotten. Vault's dynamic secrets generate short-lived, just-in-time credentials (database users,
cloud IAM keys, PKI certificates) that expire automatically: nothing to rotate, nothing to leak
long-term. This playbook implements dynamic secrets for the highest-value credential types, with the
auth methods and policies that make it usable.

## When to use
- Eliminating long-lived database credentials, cloud access keys, and shared secrets from apps and
  configs.
- After incidents involving leaked or stolen static credentials.
- Meeting secrets-management requirements (SOC 2, PCI DSS, internal policy) with a scalable
  solution.
- Before scaling microservices: dynamic credentials prevent the secrets-sprawl crisis.
- As the credential-issuance layer beneath the broader secrets-management program.

## Prerequisites
- A Vault cluster deployed, hardened, unsealed reliably (auto-unseal), with backup/restore tested.
- Target systems identified: databases, cloud accounts, PKI needs — prioritized by credential risk.
- Auth methods chosen: Kubernetes auth, AWS IAM auth, OIDC/JWT, AppRole — matched to workload types.
- Application teams ready to integrate (SDK, agent injector, or CSI provider — code changes needed).
- Break-glass and DR procedures: Vault is critical infrastructure — plan for its outage.

## Procedure
1. **Harden Vault itself first.** TLS everywhere, auto-unseal with HSM/cloud KMS, audit devices
   enabled (file + syslog), Shamir or managed root-token handling (root token revoked after initial
   setup), and network restriction (Vault is not internet-facing). Test backup/restore and the
   seal/unseal runbook before issuing a single secret.
2. **Start with database dynamic secrets.** Enable the database secrets engine for your highest-risk
   databases: configure rotation statements, default TTLs (short — hours, not days), and max TTLs.
   Applications request credentials at startup (or via agent sidecar) instead of reading static
   passwords. Verify: credentials actually expire and apps handle renewal.
3. **Add cloud dynamic secrets.** Enable AWS/GCP/Azure secrets engines to mint short-lived IAM
   credentials / service-account keys for workloads. This kills the long-lived cloud access key
   problem — workloads get credentials that die in minutes to hours, scoped to least-privilege
   roles.
4. **Deploy PKI for certificates.** Use Vault PKI as an internal CA for service-mesh mTLS, internal
   TLS, and workload identities: short-lived certificates (days/weeks) with automated issuance and
   renewal. Document the CA hierarchy, and keep offline root practices for the trust anchor.
5. **Choose auth methods per workload.** Kubernetes: k8s auth with bound service accounts and
   namespaces. VMs: AWS/GCP IAM auth or AppRole with wrapped secret IDs. Humans: OIDC to the IdP
   with MFA. CI/CD: JWT/OIDC federation (no long-lived Vault tokens in pipelines). Each method gets
   least-privilege policies — Vault policies are the authorization layer; write them carefully.
6. **Write least-privilege Vault policies.** Policies grant: which secret engines, which paths,
   which capabilities (read vs. create vs. update). Deny by default; scope by identity metadata
   (namespace, service account, team). Review policies like code — over-broad Vault policies
   recreate the sprawl Vault was meant to fix.
7. **Integrate applications properly.** Preferred patterns: Vault Agent sidecar/injector (no code
   changes, template-rendered secrets), CSI provider for Kubernetes, or SDK for custom needs.
   Applications must handle: renewal, revocation, and Vault outages (cached credentials with
   graceful degradation — never hard-code fallbacks to static secrets).
8. **Handle the static-secret remainder.** Some credentials can't be dynamic (third-party API keys,
   legacy systems): store as KV with rotation procedures and short TTLs where possible, plus
   rotation automation (custom plugins or scheduled jobs). Track the static inventory separately —
   the goal is shrinking it.
9. **Monitor Vault as critical infrastructure.** Alert on: seal status, leader changes, audit-device
   failures (losing audit is a security event), auth failures spikes, token/lease anomalies, and
   policy changes. Vault telemetry is high-signal — a compromised Vault compromises everything
   downstream.
10. **Govern and report.** Quarterly: policy reviews (least-privilege drift), auth-method audits,
    static-secret inventory shrinkage, lease/TTL compliance, and DR test results. Metrics: percent
    of credentials dynamic vs. static, mean credential lifetime (target: hours), and secrets-related
    incidents before/after.

## Expected outputs
- Hardened Vault cluster (auto-unseal, audit devices, tested DR) with root token revoked.
- Dynamic secrets for databases, cloud IAM, and PKI with short TTLs and verified expiry.
- Auth methods per workload type (k8s, cloud IAM, OIDC, JWT) with least-privilege policies.
- Application integration via agent/injector/CSI with renewal and outage handling.
- Shrinking static-secret inventory, Vault health monitoring, and quarterly governance.

## Pitfalls
- Vault as a static-secret store only: KV without dynamic secrets is an expensive password manager.
  Dynamic engines are the point.
- Over-broad policies: "read everything" Vault policies for all workloads recreate credential sprawl
  inside the vault. Least-privilege per identity.
- No outage planning: applications that hard-fail when Vault is unreachable turn Vault into a single
  point of failure. Cache, degrade gracefully, test.
- Long TTLs: 30-day "dynamic" credentials are static credentials with extra steps. Hours, not days —
  tune to the workload's tolerance.
- Neglected audit devices: Vault's audit log is the record of who accessed what secret. Losing it
  (disk full, misconfiguration) is a security incident — monitor it.

## References
- HashiCorp Vault documentation (secrets engines, auth methods, policies, agent)
- NIST SP 800-57 (key/credential lifecycle management)
- NIST SP 800-53 IA-2, SC-12 (identification, key management)
- CIS guidance on secrets management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
