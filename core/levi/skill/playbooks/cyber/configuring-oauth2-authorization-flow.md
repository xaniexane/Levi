---
skill_id: cyber_configuring_oauth2_authorization_flow
name: Configuring OAuth 2.0 Authorization Flows
description: Harden OAuth 2.0 and OpenID Connect deployments by choosing safe grant types and enforcing token hygiene.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, web]
version: 1.0.0
---
## Purpose

Configure OAuth 2.0 (with OpenID Connect) so that authorization decisions are made safely: correct grant type per client type, short-lived tokens, strict redirect-URI validation, and PKCE everywhere. Misconfigured OAuth is a classic account-takeover path — this playbook is the defensive baseline.

## When to use

- Integrating a new application with an identity provider (Entra ID, Okta, Keycloak, Auth0) or standing up your own authorization server.
- Auditing an existing OAuth deployment for token theft, redirect abuse, or overly broad scopes.
- Migrating from the legacy implicit grant to Authorization Code + PKCE.
- Reviewing third-party app registrations before approving their permissions.

## Prerequisites

- An inventory of client types in the deployment: server-side web apps, SPAs, native/mobile apps, machine-to-machine services.
- Administrative access to the authorization server / IdP admin console.
- A test tenant or staging client for validating configuration changes before production rollout.
- TLS 1.2+ enforced on all endpoints; client secrets stored in a vault, never in code or repos.

## Procedure

1. **Assign one grant type per client type.** Server-side web apps: Authorization Code flow. SPAs and native/mobile apps: Authorization Code + PKCE (S256), never the implicit grant. Service-to-service: client credentials. Decommission the implicit and resource-owner-password-credentials grants everywhere — both leak tokens to the front channel and are deprecated by the IETF security BCP.
2. **Enforce PKCE on all public clients.** Require `code_challenge`/`code_verifier` with the S256 method. On the authorization server side, reject authorization requests from public clients that lack a challenge.
3. **Lock down redirect URIs.** Register exact URIs — scheme, host, port, and path — with no wildcards and no open redirects. For native apps, use HTTPS or claimed-URL redirect schemes instead of custom schemes where possible. Log and alert on authorization requests with unregistered redirect URIs.
4. **Minimize scopes and lifetimes.** Request the narrowest scopes that work (`openid profile email` plus only what the app needs). Set access-token lifetimes short (5–15 minutes) and refresh-token lifetimes bounded (hours, not months), with refresh-token rotation enabled. Require re-authentication for high-risk actions.
5. **Secure the tokens at rest and in transit.** Store tokens server-side where possible; if a browser must hold one, use `HttpOnly` + `Secure` + `SameSite=Lax` cookies rather than `localStorage`. Never put tokens in URLs, referrers, or client-side logs.
6. **Validate tokens rigorously on the resource server.** Verify the JWT signature against the IdP's published JWKS (with key-id matching and rotation support), and check `iss`, `aud`, `exp`, `iat`, and `nonce` claims. Reject tokens that fail any check rather than degrading to permissive parsing.
7. **Add state and nonce anti-CSRF/replay protections.** Generate a cryptographically random `state` per authorization request and bind it to the user's session; use `nonce` for ID tokens. Reject responses where either value is missing or mismatched.
8. **Harden the client registration process.** Treat app registration as a privileged action: require owner attestation, review requested scopes and permissions, expire unused registrations, and periodically audit consented apps for over-privileged grants (this is where malicious consent-grant attacks hide).
9. **Monitor OAuth-specific telemetry.** Alert on: spikes in authorization errors (`invalid_grant`, `unauthorized_client`), token requests from unexpected ASNs or geographies, consent grants to newly registered apps, and refresh-token reuse (rotation detection). Feed these into the SIEM with the client ID and redirect URI attached.

## Expected outputs

- A documented grant-type mapping per application with PKCE enforced on all public clients.
- An exact-match redirect-URI registry and a periodic audit schedule.
- Token-lifetime policy (access 5–15 min, bounded rotating refresh tokens) applied across clients.
- SIEM detections for consent abuse, refresh-token reuse, and redirect-URI anomalies.

## Pitfalls

- Enabling the implicit grant "for a quick prototype" and never turning it off — tokens leak through browser history and referrers.
- Wildcard redirect URIs, which turn any open redirect on the domain into a token-theft primitive.
- Treating `aud`/`iss` validation as optional — skipped validation is how token-substitution attacks succeed.
- Confusing client credentials flow with user delegation — M2M tokens must never carry user scopes.
- Skipping refresh-token rotation: without it, a stolen refresh token is valid until expiry.

## References

- RFC 6749 (OAuth 2.0 Authorization Framework) and RFC 8252 (OAuth 2.0 for Native Apps)
- IETF OAuth Security BCP (draft-ietf-oauth-security-topics) — deprecates implicit and ROPC grants
- OpenID Connect Core 1.0 — ID token validation requirements
- MITRE ATT&CK T1550 (Use Alternate Authentication Material) for token-abuse detection context
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
