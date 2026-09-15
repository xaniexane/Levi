---
skill_id: cyber_implementing_zero_trust_with_hashicorp_boundary
name: Implementing Zero Trust with HashiCorp Boundary
description: Broker privileged session access with HashiCorp Boundary using identity-based authorization.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, pam, boundary]
version: 1.0.0
---
## Purpose
This playbook deploys HashiCorp Boundary as the session broker for privileged access: users authenticate with their identity, get authorized per-target sessions, and credentials are injected by the platform — no standing network access, no shared passwords.

## When to use
- Admins currently SSH/RDP directly to hosts over VPN with shared or static credentials.
- You need audited, just-in-time privileged sessions without a heavyweight PAM suite.
- Dynamic infrastructure (cloud, Kubernetes) where static jump hosts do not scale.

## Prerequisites
- Boundary controllers and workers deployed with TLS; OIDC provider integrated for human auth.
- Credential store configured (Vault or static store) for credential injection.
- Target inventory: hosts, services, and the roles allowed to reach each.

## Procedure
1. **Deploy the control plane.** Stand up controllers (HA) and workers near target networks; workers make outbound connections only, so targets stay unexposed.
2. **Integrate identity.** Connect OIDC so every session maps to a real user and group; disable local password auth for humans.
3. **Define scopes, targets, and roles.** Model your org hierarchy in scopes; create targets per host/service and grant roles least-privilege session rights.
4. **Enable credential injection.** Store privileged credentials in Vault; configure Boundary to inject them into sessions so users never see or handle them.
5. **Record sessions.** Enable session recording for privileged targets; protect recordings with retention policy and access control.
6. **Migrate access paths.** Publish Boundary as the only path to admin protocols; firewall off direct SSH/RDP from user networks and monitor for bypass attempts.
7. **Audit continuously.** Review session logs for anomalous targets, off-hours access, and policy changes; recertify role grants quarterly.

8. **Integrate with ticketing.** Auto-create access-request tickets from denied sessions so legitimate needs get provisioned instead of driving shadow access.
9. **Back up the control plane.** Maintain tested backups of Boundary configuration and Vault data; losing the broker must not mean losing all administrative access.

## Expected outputs
- Boundary deployment with identity-integrated, per-target session brokering.
- Credential injection configured; no standing credential knowledge by users.
- Session recordings and audit logs feeding the SIEM.
- Example: an on-call engineer authenticates via SSO, receives a 2-hour SSH session to a single production host with the credential injected, and the full session is recorded for audit.

## Pitfalls
- Leaving direct network paths to targets open, making Boundary a suggestion rather than a control.
- Overly broad targets (whole subnets) that defeat least-privilege intent.
- Session recordings stored without access control become a credential treasure chest.

- Workers deployed with overly broad network reach; scope each worker's egress to only the targets it serves.
- Session recordings retained indefinitely without a legal hold policy; define retention and purge like any other sensitive log.

## References
- HashiCorp Boundary documentation (developer.hashicorp.com/boundary).
- NIST SP 800-207, Zero Trust Architecture.
- HashiCorp Vault documentation (developer.hashicorp.com/vault) — credential store integration.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
