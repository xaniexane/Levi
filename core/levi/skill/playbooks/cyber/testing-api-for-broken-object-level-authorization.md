---
skill_id: cyber_testing_api_for_broken_object_level_authorization
name: Testing APIs for Broken Object Level Authorization
description: Authorized BOLA/IDOR testing: verify every object reference enforces per-user authorization.
risk: low
permissions: []
requires_confirmation: false
tags: [api, authorization, testing]
version: 1.0.0
---
## Purpose
Broken Object Level Authorization (BOLA, the API form of IDOR) is the most common API vulnerability: endpoints that check authentication but not whether the caller owns the requested object. This playbook covers authorized testing of your own APIs to find missing object-level checks, plus logging and detection guidance.

## When to use
- Security testing of any API exposing object IDs (orders, users, documents, accounts).
- After adding new endpoints or changing authorization logic.
- Validating fixes for a reported BOLA finding.
- Designing authorization test automation for CI.

## Prerequisites
- Written authorization and at least two test accounts with distinct data ownership.
- API documentation or traffic captures mapping endpoints to object types.
- Proxy tooling (Burp/ZAP) for request manipulation.
- Understanding of the intended authorization model per resource.

## Procedure
1. Inventory endpoints that accept object identifiers in paths, query strings, or bodies.
2. With two test accounts (A owns object 1, B owns object 2), authenticate as B and request A's objects.
3. Test read, update, and delete operations, not just reads; BOLA often differs by method.
4. Try predictable ID enumeration, UUID swapping, and nested object references (e.g. `/orders/1/items/2`).
5. Check indirect paths: search, export, and bulk endpoints that may leak other users' objects.
6. Verify the fix pattern: server-side ownership check on every object access, using indirect or capability-based references where appropriate.
7. Confirm verbose errors do not leak object existence (differential responses enable enumeration).
8. Add regression tests: automated BOLA checks in CI for every object endpoint.
9. Test GraphQL resolvers for field-level authorization; REST-focused tests miss them.
10. Re-run BOLA tests with caching enabled; caches can serve one user's object to another.
11. Test batch endpoints that accept arrays of object IDs, a common BOLA blind spot.

## Expected outputs
- BOLA finding reports with accounts, endpoints, and request/response evidence.
- Authorization model gaps documented per resource type.
- Regression tests and detection queries for anomalous cross-account access.
- GraphQL field-level authorization test results.
- Cache-enabled BOLA test results.
- Batch-endpoint authorization assessment.

## Pitfalls
- Testing only GET misses the write-side BOLA that causes real damage.
- UUIDs are not authorization; unguessable IDs reduce but do not remove the need for checks.
- Bulk and export endpoints are frequently missed in BOLA reviews.
- Fixing one endpoint while leaving the same pattern elsewhere is the classic incomplete remediation.
- Caching layers can serve one user's object to another; test with caches enabled.
- GraphQL's flexibility multiplies BOLA surface; test resolvers, not just top-level queries.
- Soft-deleted objects often remain accessible; verify authorization covers them.
- Object IDs in webhook payloads deserve the same authorization checks as API responses.

## References
- OWASP API Security Top 10: API1 Broken Object Level Authorization.
- OWASP Web Security Testing Guide: testing for IDOR.
- PortSwigger Web Security Academy: access control.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
