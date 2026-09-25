---
skill_id: cyber_implementing_api_key_security_controls
name: Implementing API Key Security Controls
description: Manage API keys securely across their lifecycle: issuance, scoping, storage, rotation, revocation, and leaked-key response.
risk: low
permissions: []
requires_confirmation: false
tags: [api, secrets, identity]
version: 1.0.0
---
## Purpose

API keys are long-lived bearer credentials that frequently leak (code
repositories, logs, client-side apps) and are often over-scoped. This
playbook covers the full API-key lifecycle: secure issuance, least-
privilege scoping, safe storage, rotation, revocation, and responding to
leaked keys.

## When to use

- Designing API authentication for new services.
- Remediating leaked API keys found in repositories or logs.
- Auditing existing API-key hygiene (scope, age, usage).
- Meeting compliance requirements for credential management.

## Prerequisites

- An API-key management system or gateway with lifecycle support
  (issuance, scoping, rotation, revocation).
- A secrets manager for server-side key storage.
- Secret-scanning in CI/CD and repositories.
- Defined key-tiers mapping to data sensitivity and rate limits.

## Procedure

1. **Issue keys with least privilege.** Scope every key: specific APIs
   and endpoints, read vs. write, IP allow-listing where consumers
   have stable egress, and rate-limit tiers. Default to the narrowest
   scope that works — broad keys are the norm and the problem.
2. **Prefer stronger alternatives where possible.** API keys are bearer
   tokens with no expiry by default — prefer short-lived OAuth2 tokens
   or mTLS for high-sensitivity access, reserving simple API keys for
   low-risk, server-to-server identification scenarios.
3. **Store keys safely.** Server-side keys live in a secrets manager,
   injected at runtime — never in code, config files, or container
   images. Never issue keys to browser or mobile clients directly;
   use a backend-for-frontend or short-lived token exchange instead.
4. **Make keys identifiable and auditable.** Use key prefixes
   identifying the environment and key ID (the prefix is not secret;
   the secret portion is), log every key's usage (endpoint, volume,
   source IPs), and attribute usage to owners for anomaly detection.
5. **Rotate on a schedule and on events.** Define rotation intervals
   per key tier, support overlapping old/new keys during rotation
   windows, and rotate immediately on personnel changes, suspected
   compromise, or scope changes.
6. **Scan for leaks continuously.** Run secret scanning on all
   repositories, CI logs, and published artifacts; monitor public
   sources (public GitHub, Pastebin-class sites) for your key
   prefixes. Treat every leak finding as an incident until scoped.
7. **Respond to leaks decisively.** On confirmed leak: revoke the key
   immediately, issue a replacement, review the key's usage logs for
   unauthorized activity during the exposure window, and determine how
   the leak happened to fix the process.
8. **Audit key hygiene regularly.** Report on: keys older than policy,
   unused keys (revoke them), over-scoped keys, and keys without
   owners. Hygiene metrics drive the program.

## Expected outputs

- An API-key policy: tiers, scopes, lifetimes, and rotation rules.
- Key inventory with ownership, scope, age, and usage.
- Secrets-manager integration for all server-side keys.
- Secret-scanning coverage with leak-response runbook.
- Hygiene metrics and review cadence.

## Pitfalls

- Using API keys where short-lived tokens belong — keys do not
   expire on their own; prefer OAuth2 for user-context and
   high-sensitivity access.
- Client-side keys (mobile apps, SPAs) are extractable by design —
   treat them as identifiers, not secrets, and enforce server-side
   authorization.
- Rotation without overlap windows breaks consumers — support dual-
   active keys during migration.
- Logging the full key value — log key IDs/prefixes, never secrets.
- Orphaned keys from departed owners — tie key lifecycle to owner
   lifecycle with automatic expiry.

## References

- OWASP: API Security Top 10 (broken authentication sections)
- NIST SP 800-63B: authenticator lifecycle guidance
- Cloud/API-gateway vendor key-management documentation
- GitHub secret-scanning and push-protection documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
