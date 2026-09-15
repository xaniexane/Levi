---
skill_id: cyber_testing_for_broken_access_control
name: Testing for Broken Access Control
description: Authorized testing for vertical and horizontal access control failures in web applications and APIs.
risk: low
permissions: []
requires_confirmation: false
tags: [api, access-control, testing]
version: 1.0.0
---
## Purpose
Broken access control remains the top web risk category: users accessing functions or data beyond their privileges. This playbook covers authorized testing for both vertical (role) and horizontal (user-to-user) failures in your own applications, with attention to the API and multi-step flows where these bugs hide.

## When to use
- Security assessment of applications with roles or multi-tenancy.
- After authorization refactors or new feature launches.
- Validating a reported privilege-escalation issue.
- Building authorization regression tests for CI.

## Prerequisites
- Written authorization and test accounts for each role plus two same-role users.
- Application map: roles, privileged functions, and tenant boundaries.
- Proxy tooling for request replay and parameter manipulation.
- Understanding of the intended access model.

## Procedure
1. Enumerate privileged functions and URLs; attempt each as a low-privilege and unauthenticated user (vertical test).
2. Replay same-role requests with swapped identifiers to test horizontal separation.
3. Test hidden endpoints: unlinked admin paths, old API versions, and debug routes.
4. Manipulate parameters that imply privilege: `role=admin`, `tenantId`, cookies, and JWT claims.
5. Test multi-step flows by skipping steps or replaying steps out of order.
6. Check that 403 responses are consistent; differential behavior can leak the existence of privileged resources.
7. Verify fixes enforce authorization server-side on every request, not just by hiding UI elements.
8. Add automated tests: each privileged endpoint tested with each role on every release.
9. Include IDOR-style object reference tests within horizontal testing, not as a separate pass.
10. Review feature-flag scoping; flags can expose privileged endpoints to broader audiences.
11. Test API versioning: old versions often lack the access checks added to new ones.

## Expected outputs
- Access-control test matrix: function, role tested, expected vs actual result.
- Findings with privilege-escalation impact assessment.
- Regression test suite for authorization.
- Feature-flag access review results.
- Per-API-version access-control comparison.
- Horizontal test matrix with object-reference coverage.

## Pitfalls
- Testing only the UI misses API-level bypasses; test the endpoints directly.
- Client-side role checks are cosmetic; every finding must be verified server-side.
- Multi-tenant bugs often appear in search, export, and webhook endpoints, not just CRUD.
- Fixing the reported URL while leaving the same check missing elsewhere is the standard incomplete fix.
- Feature flags can expose privileged endpoints to broader audiences; review flag scoping.
- Old API versions frequently lack newer access checks; test every live version.
- Deny-by-default is the goal; every new endpoint needs an explicit authorization decision.
- Scheduled jobs and async workers often run with elevated privilege; review their authorization context.

## References
- OWASP Top 10: Broken Access Control (owasp.org/www-project-top-ten).
- PortSwigger Web Security Academy: access control vulnerabilities.
- OWASP Web Security Testing Guide: authorization testing.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
