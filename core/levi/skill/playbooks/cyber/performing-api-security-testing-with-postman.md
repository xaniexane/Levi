---
skill_id: cyber_performing_api_security_testing_with_postman
name: Performing API Security Testing with Postman (Authorized)
description: Security-test your own APIs using Postman collections for auth, input, and logic flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, api-security, testing]
version: 1.0.0
---

## Purpose
This playbook uses Postman for structured security testing of APIs your organization owns or is authorized to test: building attack-oriented collections that probe authentication, authorization, input handling, and business-logic flaws. Never test APIs you are not authorized to assess.

## When to use
- Your team already uses Postman for functional API testing and wants a security layer.
- Manual security review of your APIs before release or after significant changes.
- Reproducing reported API vulnerabilities with shareable, repeatable collections.

## Prerequisites
- Written authorization and a non-production test environment with test accounts at multiple privilege levels.
- Postman with environments configured for the target API; no production credentials in shared workspaces.
- The API specification and knowledge of intended authorization rules per endpoint.

## Procedure
1. **Scope and set up.** Document the APIs, test accounts (admin, user, unauthenticated), and the test environment; create Postman environments per role so privilege levels are explicit.
2. **Test authentication.** Verify endpoints reject missing, expired, and tampered tokens; check for authentication on every endpoint, including "internal" or undocumented ones.
3. **Test authorization (BOLA/BFLA).** With a low-privilege token, attempt to access other users' objects by ID (BOLA) and admin-only functions (BFLA); record every improper grant.
4. **Test input handling.** Send malformed, oversized, and type-confused inputs; check for injection (SQL, NoSQL, command), verbose errors, and mass-assignment of unexpected fields.
5. **Test business logic.** Probe rate-sensitive flows (coupons, transfers, voting), state transitions out of order, and race conditions with collection runner iterations.
6. **Check security headers and transport.** Verify TLS enforcement, security headers, CORS policy restrictiveness, and that sensitive data is not over-exposed in responses.
7. **Package and file.** Save the security collection with test scripts asserting expected denials; file findings with request/response evidence and re-run the collection after fixes.

8. **Test for mass assignment.** Send unexpected fields (role, isAdmin, price) in update requests; APIs that silently accept them have a mass-assignment flaw.
9. **Keep collections current.** Update the security collection when the API changes; a stale collection testing last quarter's API is security theater.

## Expected outputs
- Postman security collection with role-based environments and assertion scripts.
- Findings report with evidence, severity, and remediation guidance.
- Regression collection re-run per release.
- Example: a low-privilege token successfully retrieves another user's order history by changing the ID in the path (BOLA); the collection's test script asserts a 403 for this case and fails until the fix is deployed.

## Pitfalls
- Testing against production with real user data or aggressive request volumes.
- Storing real credentials or tokens in shared Postman workspaces.
- Confusing functional test passage with security: a 200 OK is not proof of correct authorization.

## References
- OWASP API Security Top 10 (owasp.org/API-Security).
- Postman security testing guidance (learning.postman.com/docs).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
