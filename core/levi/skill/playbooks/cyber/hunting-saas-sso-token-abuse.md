---
skill_id: cyber_hunting_saas_sso_token_abuse
name: Hunting SaaS SSO Token Abuse
description: Detect stolen SSO/session-token abuse in SaaS: impossible travel, token replay, refresh-token anomalies, and consent-grant abuse.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, identity, saas]
version: 1.0.0
---
## Purpose

Modern intrusions increasingly bypass endpoints entirely, operating with
stolen SSO tokens directly against SaaS APIs. This playbook covers
hunting for session-token theft and replay: anomalous token use in
identity-provider logs, refresh-token abuse, and malicious OAuth consent
grants that persist beyond password resets.

## When to use

- Investigating business-email compromise or SaaS-based intrusions.
- After credential-phishing: assume tokens were stolen alongside
  passwords and hunt for their use.
- Validating conditional-access and token-protection policies.
- Proactive identity-threat hunting on IdP logs.

## Prerequisites

- Identity-provider sign-in and audit logs (Entra ID, Okta, Google
  Workspace) with token-issuance, refresh, and usage events.
- Baselines of normal SSO behavior per user: devices, locations,
  applications, and session lifetimes.
- Inventory of authorized OAuth applications and their granted scopes.
- Understanding of your token lifetimes and conditional-access policies.

## Procedure

1. **Hunt impossible-travel and velocity anomalies.** Flag sessions
   where the same user or token appears from geographically
   impossible locations in short windows, or where a token issued to
   one device/IP is suddenly used from another ASN or country.
2. **Hunt token-replay indicators.** Look for: access tokens used
   without the corresponding interactive sign-in, user agents
   inconsistent with the enrolled device, and API access patterns
   (bulk mail reads, file enumeration) inconsistent with the user's
   normal behavior.
3. **Hunt refresh-token abuse.** Monitor for refresh tokens used from
   new devices or locations, unusually long-lived sessions that
   survive password resets (the classic token-theft persistence), and
   token families with anomalous refresh chains.
4. **Hunt malicious consent grants.** Review OAuth application consents:
   apps granted mail/file read-write scopes outside IT process,
   consent granted immediately after a phishing-suspected sign-in, and
   multi-tenant apps with broad permissions. Attackers use these for
   persistent API access that survives credential rotation.
5. **Check for MFA-bypass patterns.** Look for sign-ins that bypassed
   MFA via legacy protocols (IMAP/POP/SMTP auth), trusted-location
   abuse, or MFA-fatigue approvals preceding token issuance —
   these are the theft vectors to close.
6. **Correlate with endpoint and phishing telemetry.** Tie token abuse
   to its source: phishing emails clicked, adversary-in-the-middle
   infrastructure, or malware-observed token theft. The full chain
   informs both scoping and prevention.
7. **Respond decisively.** Revoke all sessions and refresh tokens for
   affected users, remove malicious OAuth grants, reset passwords,
   enforce re-authentication, and review what data the abused tokens
   accessed (mail, files, chats) for breach-notification decisions.
8. **Harden token security.** Enforce phishing-resistant MFA, block
   legacy authentication, implement token-protection / device-bound
   sessions where available, require admin consent for OAuth apps,
   and shorten token lifetimes for high-risk users.

## Expected outputs

- Token-abuse findings: users, tokens, locations, and accessed data.
- Malicious OAuth grants identified and revoked.
- Theft-vector analysis (phishing, AiTM, malware) per case.
- Session/token revocation and re-authentication records.
- Hardening changes: MFA, legacy-auth blocks, consent governance.

## Pitfalls

- Password resets do not revoke stolen OAuth grants or all token
   types — revocation must be explicit and comprehensive.
- Travel and VPN use create impossible-travel false positives —
   baseline per user and corroborate with device signals.
- Focusing only on interactive sign-ins — API-only token abuse is
   invisible to sign-in-log-only hunts; include audit/API logs.
- Legacy protocol blocking can break scanners and service accounts —
   inventory before enforcing.
- Attackers register their own "verified" apps — do not trust
   publisher verification alone; review scopes and necessity.

## References

- MITRE ATT&CK: T1550 (Use Alternate Authentication Material),
  T1136-adjacent cloud persistence; T1528 (Steal Application Access
  Token)
- CISA: MFA and phishing-resistant authentication guidance
- Identity-provider documentation (sign-in log schemas, token
  revocation, consent management)
- NIST SP 800-63B: authenticator assurance guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
