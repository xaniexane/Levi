---
skill_id: cyber_testing_for_json_web_token_vulnerabilities
name: Testing for JSON Web Token Vulnerabilities
description: Authorized JWT testing: algorithm confusion, none algorithm, weak secrets, and claim trust issues.
risk: low
permissions: []
requires_confirmation: false
tags: [api, jwt, testing]
version: 1.0.0
---
## Purpose
JWTs are frequently validated incorrectly: accepting `alg: none`, confusing symmetric and asymmetric algorithms, or trusting unsigned claims. This playbook covers authorized testing of your own APIs' JWT handling to find these flaws, and the strict validation profile that fixes them.

## When to use
- Security assessment of APIs using JWTs for authentication or authorization.
- After changing identity providers, libraries, or key rotation procedures.
- Validating a reported JWT bypass.
- Designing token validation standards for development teams.

## Prerequisites
- Written authorization and test accounts with JWT-issuing flows.
- Sample tokens and knowledge of the expected issuer, audience, and algorithms.
- Proxy tooling and a JWT manipulation toolkit.
- Access to the validation code or library configuration.

## Procedure
1. Decode tokens and document the header, claims, and key source (shared secret vs JWKS).
2. Test `alg: none`: strip the signature and see if the token is accepted.
3. Test algorithm confusion: sign an RS256 token's payload with the public key as HMAC where applicable.
4. Test weak secrets: brute-force short HMAC secrets with a controlled wordlist.
5. Tamper claims: elevate roles, extend expiry, swap subject, change issuer; observe acceptance.
6. Test `kid`/`jku`/`x5u` header injection where the library fetches keys from attacker-influenced locations.
7. Verify the fix: explicit algorithm allowlist, signature verification with the correct key, and validation of iss, aud, exp, and nbf.
8. Re-test every bypass variant after the fix; libraries differ in defaults.
9. Test key rotation procedures; stale keys validating new tokens is a real incident pattern.
10. Verify that signing keys are segmented per environment, not shared between dev and prod.
11. Check token validation in every service, not just the gateway; defense in depth matters.

## Expected outputs
- JWT test matrix: attack variant, token used, accepted/rejected.
- Findings with privilege-escalation impact.
- Validation profile (algorithms, claims, key source) and retest evidence.
- Key rotation procedure test results.
- Per-environment key segmentation audit.
- Per-service validation consistency report.

## Pitfalls
- Library defaults are the usual culprit; read the validation code, not just the docs.
- Accepting multiple algorithms widens confusion attacks; pin to one.
- Long-lived tokens amplify every other flaw; keep lifetimes short with refresh rotation.
- Key confusion between environments (dev keys validating prod tokens) is a real incident pattern.
- Multiple services sharing one signing key means one compromise breaks all; segment keys.
- Accepting tokens past a generous clock-skew window extends replay opportunity.
- Key IDs that map to files on disk invite path traversal; validate kid values.
- Tokens logged by proxies or APM tools become long-lived secrets; audit log redaction.

## References
- OWASP JWT Cheat Sheet.
- RFC 8725 (JWT best practices).
- PortSwigger Web Security Academy: JWT attacks.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
