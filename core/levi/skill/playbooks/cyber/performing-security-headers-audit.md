---
skill_id: cyber_performing_security_headers_audit
name: Security Headers Audit
description: Audit HTTP security headers across web properties and remediate gaps to reduce client-side attack surface.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, headers, hardening]
version: 1.0.0
---

## Purpose
- Measure how consistently security headers are deployed across the organization's web properties.
- Reduce client-side risks: clickjacking, MIME confusion, XSS impact, and information leakage.
- Give application teams a concrete, testable header baseline to implement.
- Track header compliance over time as applications change.

## When to use
- During web application security assessments and pre-release reviews.
- When standardizing a secure baseline across many applications.
- After incidents involving clickjacking, MIME-sniffing, or cache poisoning.
- As a recurring automated check in CI/CD pipelines.

## Prerequisites
- An inventory of in-scope applications, domains, and environments.
- A header baseline policy defining required headers and values for the organization.
- Scanning tooling: a header scanner or custom scripts plus manual verification capability.
- Application team contacts for remediation follow-up.

## Procedure
1. Finalize the header baseline: Strict-Transport-Security, Content-Security-Policy, X-Frame-Options or frame-ancestors, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
2. Scan every in-scope application and record the full response headers for representative pages and API endpoints.
3. Check HSTS: presence, max-age of at least one year, includeSubDomains, and preload where appropriate.
4. Evaluate Content-Security-Policy for unsafe-inline, unsafe-eval, wildcard sources, and missing object-src restrictions.
5. Verify framing protections: frame-ancestors directives or X-Frame-Options DENY or SAMEORIGIN on all pages.
6. Check for information leakage in Server, X-Powered-By, and similar headers; suppress or generalize them.
7. Test cookie flags in parallel: Secure, HttpOnly, and SameSite on session and sensitive cookies.
8. Validate that security headers are present on error pages, redirects, and API responses, not just the homepage.
9. Score each application against the baseline and prioritize gaps by exploitability.
10. Provide teams with copy-paste configuration snippets for their web server or framework.
11. Retest after remediation and add header checks to automated pipeline gates.
12. Trend compliance over time and report to application security leadership.

## Expected outputs
- A per-application header compliance scorecard against the baseline.
- Remediation guidance with configuration snippets per platform.
- Automated header checks integrated into CI/CD.
- Trend reporting on header compliance.
- A header baseline policy document owned by application security.
- Exceptions register for applications with documented business reasons for deviations.

## Pitfalls
- Deploying a strict CSP without report-only testing first, which breaks legitimate application functionality.
- Auditing only the homepage while inner pages and APIs lack protections.
- Setting HSTS with includeSubDomains before confirming every subdomain supports HTTPS.
- Treating headers as a substitute for fixing the underlying vulnerabilities they mitigate.
- Scanning only production; staging and pre-prod often lag behind.

## References
- securityheaders.com scan documentation for methodology reference
- OWASP Secure Headers Project
- Mozilla Observatory documentation on header best practices
- NIST SP 800-53 control SC-8 on transmission confidentiality
- RFC 6797 on HTTP Strict Transport Security
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
