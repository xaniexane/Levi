---
skill_id: cyber_testing_for_sensitive_data_exposure
name: Testing for Sensitive Data Exposure
description: Authorized testing for sensitive data leaks in responses, logs, URLs, and error messages.
risk: low
permissions: []
requires_confirmation: false
tags: [web, data-protection, testing]
version: 1.0.0
---
## Purpose
Sensitive data exposure is rarely a single bug; it is data appearing where it should not: verbose API responses, logs, URLs, error messages, or caches. This playbook covers authorized testing of your own applications to find these leaks, classify what is exposed, and drive data-minimization fixes.

## When to use
- Security assessment of APIs and web applications handling personal or financial data.
- After adding new fields to API responses or log statements.
- Compliance reviews (PCI, HIPAA, GDPR data minimization).
- Investigating a suspected data leak report.

## Prerequisites
- Written authorization and test accounts with realistic (synthetic) sensitive data.
- Data classification policy: what counts as sensitive for your organization.
- Proxy tooling and log access for the test environment.
- Inventory of data stores the application touches.

## Procedure
1. Classify the data the application handles; define what must never appear in each output channel.
2. Exercise the application as a low-privilege user; capture all API responses and inspect for over-exposed fields.
3. Check URLs, referers, and browser history for tokens, IDs, or personal data.
4. Trigger errors (bad input, not-found IDs) and inspect messages and stack traces for internals.
5. Review application and infrastructure logs for sensitive values logged during the test flows.
6. Verify transport and storage: TLS everywhere, encrypted backups, masked data in non-production.
7. Drive fixes: response DTOs with minimal fields, structured logging with redaction, and error handling that hides internals.
8. Re-test each channel after fixes; exposure often moves rather than disappears.
9. Scan mobile app binaries and web bundles for hardcoded secrets as part of exposure review.
10. Audit analytics and error-reporting SDK configurations; they exfiltrate field data by default.
11. Check data exports and reports for over-collection beyond the stated purpose.

## Expected outputs
- Exposure findings per channel (response, URL, log, error, cache) with samples.
- Data-flow notes showing where sensitive fields travel.
- Remediation verification per channel.
- Hardcoded-secret scan results for client artifacts.
- Third-party SDK data-collection audit.
- Export/report data-minimization review.

## Pitfalls
- Staging with production data dumps creates the very exposure you are testing for; use synthetic data.
- Verbose errors in debug mode ship to production regularly; verify production error handling separately.
- Logs are the most commonly missed channel; grep them for the test data you submitted.
- Data minimization is a design decision; bolting redaction on later is fragile.
- Analytics and error-reporting SDKs exfiltrate field data; audit their configuration.
- Client-side bundles are public; treat anything in them as disclosed.
- Data retention beyond the stated purpose becomes a breach-multiplier; enforce retention.
- Search indexing of authenticated pages leaks data to search engines; verify robots and auth on indexed routes.

## References
- OWASP Top 10: Cryptographic Failures (owasp.org/www-project-top-ten).
- NIST SP 800-122, Guide to Protecting the Confidentiality of PII.
- PCI DSS data-protection requirements (where applicable).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
