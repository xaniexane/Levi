---
skill_id: cyber_testing_api_security_with_owasp_top_10
name: Testing API Security with the OWASP Top 10
description: Systematic authorized API security testing mapped to the OWASP API Security Top 10 categories.
risk: low
permissions: []
requires_confirmation: false
tags: [api, owasp, testing]
version: 1.0.0
---
## Purpose
The OWASP API Security Top 10 gives API testing a standard structure. This playbook maps an authorized assessment of your own APIs to each category: what to test, what evidence to collect, and how findings translate into fixes and detections. It is a methodology wrapper, not a replacement for the per-issue playbooks.

## When to use
- Planning a comprehensive API security assessment.
- Standardizing API testing methodology across teams or vendors.
- Gap analysis: which Top 10 categories lack coverage in your program.
- Pre-release security sign-off for API-driven products.

## Prerequisites
- Written authorization, scope, and test accounts for the target APIs.
- OWASP API Security Top 10 (2023) as the category reference.
- API inventory: documentation, traffic samples, and authentication details.
- Proxy and automation tooling for repeatable tests.

## Procedure
1. Build the API inventory: endpoints, methods, parameters, auth requirements, and data classification.
2. Map each endpoint to Top 10 categories: BOLA (API1), auth (API2), object property auth (API3), resource consumption (API4), function-level auth (API5), business flows (API6), SSRF (API7), misconfiguration (API8), inventory (API9), unsafe input (API10).
3. Test categories in risk order for your API: usually authorization flaws first, then auth, then injection.
4. For each category, record the test performed, the evidence, and the verdict; mark untestable items explicitly.
5. Verify business-logic categories with realistic abuse scenarios, not just technical payloads.
6. Consolidate findings into a per-category scorecard showing coverage and gaps.
7. Drive remediation per category owner: auth to identity teams, BOLA to API developers, misconfig to platform.
8. Re-test after fixes and track category-level trends across releases.
9. Include API4 (unrestricted resource consumption) with load-limited tests in staging.
10. Note untestable endpoints explicitly rather than silently skipping them.
11. Map third-party API dependencies into the inventory; your API inherits their weaknesses.

## Expected outputs
- Per-category test coverage matrix with evidence and verdicts.
- Consolidated finding list mapped to Top 10 categories.
- Trend report showing category risk across releases.
- Resource-consumption test results with safe limits documented.
- Untestable-endpoint register with reasons.
- Third-party API dependency risk notes.

## Pitfalls
- Checklist testing without threat modeling misses API-specific business logic flaws.
- API9 (improper inventory) is often skipped; shadow and deprecated endpoints are real findings.
- Automated scanners cover only a fraction of the Top 10; manual testing is required for auth categories.
- Versioned APIs multiply the work; test every supported version, including deprecated ones still live.
- Per-category coverage scores can mask depth gaps; note untested endpoints explicitly.
- Deprecated API versions still in production need the full assessment, not a pass.
- Business-logic categories need product-owner input; testers cannot invent the rules.
- Rate limiting tested only at the edge misses per-tenant limits behind the gateway.

## References
- OWASP API Security Top 10 2023 (owasp.org/API-Security).
- OWASP Web Security Testing Guide.
- NIST SP 800-95, Guide to Secure Web Services.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
