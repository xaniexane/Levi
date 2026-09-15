---
skill_id: cyber_testing_api_authentication_weaknesses
name: Testing API Authentication Weaknesses
description: Authorized testing of API authentication: credential attacks, token flaws, MFA gaps, and brute-force resistance.
risk: low
permissions: []
requires_confirmation: false
tags: [api, authentication, testing]
version: 1.0.0
---
## Purpose
Broken authentication is a perennial API Top 10 item. This playbook covers authorized testing of your own APIs' authentication: password and token flows, brute-force and credential-stuffing resistance, MFA enforcement, and session management. Findings feed both fixes and detection rules for authentication abuse.

## When to use
- Security assessment of a new or changed API.
- After authentication-related incidents or penetration test findings.
- Validating MFA rollout or password-policy changes.
- Building detection for credential-stuffing against your APIs.

## Prerequisites
- Written authorization with in-scope endpoints and test accounts.
- Test credentials at multiple privilege levels; MFA test devices.
- Understanding of the auth flows in use (OAuth2, API keys, session cookies, JWT).
- Rate-limit and lockout policy documentation to test against.

## Procedure
1. Map all authentication endpoints and flows, including mobile, web, and machine-to-machine variants.
2. Test credential brute force with a small, controlled attempt set; verify lockout or throttling engages.
3. Test credential stuffing with a handful of known-breached pairs on test accounts; confirm detection fires.
4. Attempt authentication bypasses: missing token, tampered token, parameter pollution, and HTTP method tampering.
5. Verify MFA cannot be skipped by omitting parameters, replaying sessions, or using backup flows.
6. Check session and token lifecycle: expiry, rotation on privilege change, and server-side revocation.
7. Review API key handling: issuance, scope, rotation, and revocation procedures.
8. Translate findings into detection rules: failed-auth spikes, impossible travel, token replay.
9. Test password reset and account recovery flows for enumeration and token predictability.
10. Inventory legacy auth (basic auth, static keys) that escaped the main auth review.
11. Verify that disabled accounts cannot authenticate via cached tokens or alternate endpoints.

## Expected outputs
- Authentication test report with reproducible steps per finding.
- Brute-force/lockout verification results.
- Detection rules for authentication abuse.
- Recovery-flow test results with enumeration assessment.
- Legacy authentication inventory.
- Disabled-account authentication verification.

## Pitfalls
- Aggressive brute-force testing locks out real users; use test accounts and tight attempt budgets.
- Testing in production can trigger fraud controls; prefer staging with production-equivalent config.
- A passing lockout test is not enough; verify the lockout cannot be bypassed via alternate endpoints.
- Machine-to-machine keys are often forgotten in MFA rollouts; inventory them explicitly.
- OAuth device flow and legacy basic auth often escape the main auth review; inventory them.
- Verbose auth errors enable username enumeration; standardize responses.
- Testing lockout on shared test accounts can block the whole team; use dedicated accounts.
- API versioning multiplies auth surface; test deprecated versions still in production.

## References
- OWASP API Security Top 10 (owasp.org/API-Security).
- OWASP Authentication Cheat Sheet.
- NIST SP 800-63B, Digital Identity Guidelines (Authentication).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
