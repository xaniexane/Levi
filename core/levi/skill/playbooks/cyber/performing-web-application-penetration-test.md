---
skill_id: cyber_performing_web_application_penetration_test
name: Web Application Penetration Test
description: Conduct authorized web application penetration tests with structured methodology, evidence, and remediation support.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, pentest, web]
version: 1.0.0
---

## Purpose
- This playbook covers authorized penetration testing to find and fix vulnerabilities; every test requires written permission.
- Find the vulnerabilities automated scanners miss: logic flaws, broken access control, and chained exploits.
- Give development teams actionable findings with reproduction steps and fix guidance.
- Validate that fixes actually work through retesting.

## When to use
- Before major releases and at least annually for critical applications.
- When applications handle sensitive data or privileged functions.
- After significant architectural changes or new integrations.
- When compliance frameworks require penetration testing.

## Prerequisites
- Written rules of engagement: scope, test accounts, forbidden actions, and contacts.
- A test environment mirroring production, with production testing only if explicitly authorized.
- Application documentation: architecture, user roles, and data flows.
- Coordination with operations and the SOC for the test window.

## Procedure
1. Confirm authorization, scope, and rules of engagement in writing before any testing.
2. Perform reconnaissance: map the application, enumerate endpoints, and identify technologies.
3. Test authentication: credential handling, MFA, session management, and brute-force protections.
4. Test access control: horizontal and vertical privilege escalation, IDOR, and forced browsing.
5. Test input handling: injection flaws across SQL, OS command, XSS, XXE, and template injection.
6. Test business logic: workflow bypass, race conditions, and abuse of application features.
7. Test API security: authentication, rate limiting, mass assignment, and excessive data exposure.
8. Assess cryptography and transport: TLS configuration, sensitive data handling, and token security.
9. Chain findings to demonstrate realistic impact without causing damage or accessing real user data.
10. Document each finding with severity, reproduction steps, evidence, and affected components.
11. Provide remediation guidance with code-level fix suggestions for developers.
12. Deliver the report, brief stakeholders, and retest after fixes to confirm closure.

## Expected outputs
- A penetration test report with risk-rated findings and evidence.
- Developer-ready remediation guidance.
- Retest results confirming fixes.
- A vulnerability trend report across test cycles showing program maturity.
- Secure coding training topics derived from recurring finding classes.

## Pitfalls
- Testing outside the agreed scope; scope creep creates legal and operational risk.
- Causing denial of service with aggressive scanning or fuzzing; throttle and monitor.
- Reporting scanner output without manual validation; unverified findings waste developer trust.
- Skipping the retest; unverified fixes frequently fail to close the finding.

## References
- OWASP Application Security Verification Standard for coverage criteria
- OWASP Web Security Testing Guide
- OWASP Top 10
- NIST SP 800-53 control CA-8 on penetration testing
- PTES technical guidelines for methodology structure
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
