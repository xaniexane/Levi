---
skill_id: cyber_testing_jwt_token_security
name: Testing JWT Token Security
description: Authorized end-to-end JWT security review: issuance, storage, transport, rotation, and revocation.
risk: low
permissions: []
requires_confirmation: false
tags: [api, jwt, testing]
version: 1.0.0
---
## Purpose
JWT vulnerabilities extend beyond signature bypasses into lifecycle issues: tokens in URLs, missing rotation, no revocation, and over-broad scopes. This playbook covers an authorized end-to-end review of your own applications' JWT usage, complementing the signature-focused JWT testing playbook.

## When to use
- Security review of session or API token design.
- After implementing refresh-token rotation or revocation.
- Investigating suspected token theft or replay.
- Designing token standards for microservices.

## Prerequisites
- Written authorization and test accounts across privilege levels.
- Token samples and documentation of issuance, storage, and validation.
- Proxy and mobile/web client access to observe token handling.
- Understanding of the refresh and revocation flows.

## Procedure
1. Map the token lifecycle: issuance, storage (cookie/localStorage/memory), transport, refresh, and revocation.
2. Check transport: tokens in URLs, logs, or referers; confirm Secure/HttpOnly/SameSite cookie flags where applicable.
3. Test lifetime: are access tokens short-lived, do refresh tokens rotate, and is reuse detected?
4. Test revocation: after password change, logout, or admin disable, do outstanding tokens actually die?
5. Test scope: request tokens with escalated scopes; verify the server enforces scope per endpoint.
6. Test replay: reuse tokens across devices/IPs and observe whether anomaly detection fires.
7. Review key management: rotation procedures, algorithm pinning, and separation of signing keys per environment.
8. Drive fixes: short lifetimes, rotation with reuse detection, server-side revocation lists, and minimal scopes.
9. Test token binding to device or DPoP where the threat model warrants it.
10. Monitor time synchronization across services; clock skew breaks expiry enforcement.
11. Verify that token theft detection (reuse, anomaly) actually alerts the SOC.

## Expected outputs
- Token lifecycle map with findings per stage.
- Revocation and rotation test results.
- Token security standard recommendations.
- Token-binding feasibility assessment.
- Clock-sync monitoring status.
- Token-anomaly alerting verification.

## Pitfalls
- Revocation is the most commonly missing control; test it explicitly, not by assumption.
- Refresh-token reuse detection requires server-side state; stateless designs often skip it.
- Mobile token storage (keychain/keystore vs plaintext) needs separate verification.
- Long-lived 'remember me' tokens deserve the same scrutiny as primary sessions.
- Clock skew between services causes premature expiry or over-acceptance; monitor time sync.
- Anomaly detection that never alerts is decoration; test the full alert path.
- Backup and export features often bypass token controls; include them in scope.
- Token refresh endpoints without rotation allow indefinite session extension; verify rotation.

## References
- OWASP JWT Cheat Sheet.
- RFC 8725 (JWT best practices) and RFC 9700 (OAuth security BCP).
- NIST SP 800-63B, Digital Identity Guidelines.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
