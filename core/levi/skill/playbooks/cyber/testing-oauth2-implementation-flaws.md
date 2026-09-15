---
skill_id: cyber_testing_oauth2_implementation_flaws
name: Testing OAuth 2.0 Implementation Flaws
description: Authorized OAuth 2.0 testing: redirect URI validation, PKCE, state handling, and token endpoint flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [api, oauth, testing]
version: 1.0.0
---
## Purpose
OAuth 2.0 is secure in specification and frequently broken in implementation. This playbook covers authorized testing of your own OAuth deployments: redirect URI validation, PKCE enforcement, state parameter handling, and token endpoint weaknesses that lead to code interception or token theft.

## When to use
- Security review of SSO or social-login integrations.
- After adding new OAuth clients or redirect URIs.
- Validating a reported OAuth bypass or token leak.
- Designing OAuth client standards for development teams.

## Prerequisites
- Written authorization and test client registrations (public and confidential).
- Understanding of the flows in use: authorization code, PKCE, client credentials.
- Proxy tooling for manipulating authorize and token requests.
- Access to client configuration for fix verification.

## Procedure
1. Inventory clients, redirect URIs, and flows; note which clients are public (mobile/SPA).
2. Test redirect URI validation with bypass variants: subdomains, paths, fragments, and open-redirect chaining.
3. Verify PKCE is required and enforced for public clients; test code interception without verifier.
4. Test the state parameter: missing, predictable, or unenforced state enables CSRF login attacks.
5. Test authorization code replay, code leakage via referer, and token endpoint authentication.
6. Check token storage and transmission: fragments vs query, response modes, and referrer leakage.
7. Verify scope enforcement and that issued tokens cannot be escalated.
8. Confirm fixes: exact redirect URI matching, mandatory PKCE with S256, unpredictable state, and confidential-client authentication.
9. Test PAR (pushed authorization requests) adoption to shrink request-tampering surface.
10. Minimize registered redirect URIs; each one multiplies bypass opportunities.
11. Verify token introspection and revocation endpoints behave consistently.

## Expected outputs
- OAuth test matrix per client and flow with bypass results.
- Findings with token-theft or account-takeover impact.
- Hardened client configuration and retest evidence.
- PAR adoption assessment.
- Redirect URI minimization review.
- Introspection/revocation consistency test results.

## Pitfalls
- Wildcard redirect URIs are the classic flaw; require exact matching.
- SPAs and mobile apps cannot keep secrets; PKCE is mandatory, not optional, for them.
- State validation must be cryptographic and bound to the session, not a static value.
- Legacy implicit flow should be disabled; it exposes tokens in URLs.
- Multiple redirect URIs per client multiply bypass opportunities; minimize them.
- Revocation endpoints that do not actually revoke are a common finding; test them.
- Mixing confidential and public clients under one registration confuses the security model.
- Consent screen clarity affects phishing resistance; review what users actually see.

## References
- RFC 9700 (OAuth 2.0 Security Best Current Practice).
- OWASP Cheat Sheet: OAuth2.
- PortSwigger Web Security Academy: OAuth authentication.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
