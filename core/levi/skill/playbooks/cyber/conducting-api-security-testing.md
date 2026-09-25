---
skill_id: cyber_conducting_api_security_testing
name: Conducting Authorized API Security Testing
description: Practitioner guide to planning and executing authorized API security assessments, from scoping and threat modeling to reporting.
risk: info
permissions: []
requires_confirmation: false
tags: [application-security, assessment, api]
version: 1.0.0
---
## Purpose
APIs are now the primary attack surface for many applications, and broken object-level authorization tops the risk list. This playbook structures an authorized API security assessment: scoping, documentation review, authentication and authorization testing, input validation, business-logic review, and reporting -- all within explicit written authorization.

## When to use
- Assessing a REST, GraphQL, or gRPC API before production release or major change.
- Responding to an API-related security finding or incident.
- Establishing a repeatable API testing methodology for the security team.
- Validating fixes from a previous assessment.

## Prerequisites
- Written authorization defining in-scope endpoints, environments, and testing windows.
- API documentation (OpenAPI/Swagger, GraphQL schema) and test credentials for multiple roles.
- Isolated test environment; production testing only with explicit approval and safeguards.
- Tooling: proxy (Burp Suite, OWASP ZAP), API client, and scripting for automation.

## Procedure
1. Confirm scope and rules of engagement. Document allowed endpoints, test accounts, rate-limit expectations, and prohibited actions (data destruction, DoS).
2. Map the attack surface. Inventory all endpoints, methods, parameters, and authentication requirements from documentation and traffic observation.
3. Test authentication. Verify token issuance, expiry, refresh flows, and that unauthenticated requests to protected endpoints are rejected.
4. Test authorization. With multiple role accounts, attempt cross-user and cross-role access on every object endpoint; this is where most API flaws live.
5. Test input handling. Probe for injection, mass assignment, excessive data exposure, and improper handling of unexpected types or oversized payloads.
6. Review business logic and rate limiting. Test for workflow bypasses, IDOR-adjacent logic flaws, and missing throttling on sensitive operations.
7. Assess the supporting configuration. Check CORS, security headers, error verbosity, versioning, and logging of security events.
8. Report with evidence. Document each finding with request/response evidence, impact, and remediation guidance; retest after fixes.

## Expected outputs
- Assessment report with evidenced findings ranked by risk.
- Remediation guidance mapped to API security best practices.
- Retest results confirming closure.

## Pitfalls
- Testing without written authorization is unauthorized access; get it signed first.
- Skipping authorization testing misses the most common and impactful API flaws.
- Aggressive fuzzing against production causes outages; use the test environment.
- Reports without reproducible evidence slow remediation and retesting.

## References
- OWASP API Security Top 10
- OWASP Testing Guide (API sections)
- NIST SP 800-95, Guide to Secure Web Services
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
