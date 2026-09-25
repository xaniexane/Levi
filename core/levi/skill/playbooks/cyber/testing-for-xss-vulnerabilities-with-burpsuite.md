---
skill_id: cyber_testing_for_xss_vulnerabilities_with_burpsuite
name: Testing for XSS Vulnerabilities with Burp Suite
description: Systematic authorized XSS testing workflow using Burp Suite: proxy, scanner, repeater, and collaborator.
risk: low
permissions: []
requires_confirmation: false
tags: [web, xss, burpsuite]
version: 1.0.0
---
## Purpose
Burp Suite structures XSS testing from discovery to proof. This playbook gives an authorized, repeatable workflow for your own applications: mapping the attack surface through the proxy, using scanner checks as a starting point, confirming manually in Repeater, and catching blind vectors with Collaborator. Manual verification remains mandatory; scanner output alone is not a finding.

## When to use
- Structured XSS assessment of a web application.
- Training testers on a consistent Burp-based XSS methodology.
- Validating XSS fixes across many inputs efficiently.
- Hunting blind/stored XSS that only fires in other users' sessions.

## Prerequisites
- Written authorization; Burp Suite (Community or Professional) configured as proxy.
- Test accounts and a defined scope in Burp's target scope.
- Staging environment preferred for stored-XSS testing.
- Safe confirmation payloads; Collaborator access for blind testing.

## Procedure
1. Configure the proxy, define target scope, and browse the application to map inputs and reflection points.
2. Run Burp's scanner (Professional) or manual audit checks as a first pass; treat results as leads, not findings.
3. For each reflection point, send the request to Repeater and determine the exact output context.
4. Develop context-specific payloads in Repeater; confirm execution with harmless markers.
5. Test stored vectors by submitting payloads and triggering rendering as a separate test user.
6. Use Burp Collaborator payloads for blind XSS in fields rendered in admin panels, emails, or reports.
7. Record every confirmed finding with the full request/response pair from Burp.
8. Re-test after remediation using the saved Repeater tabs and Collaborator payloads.
9. Use Burp's target analyzer to confirm every parameter was exercised at least once.
10. Verify Burp's session handling rules maintain login state; invalid sessions invalidate results.
11. Save the Burp project with scope and evidence for retest and audit purposes.

## Expected outputs
- Burp project with mapped scope, confirmed findings, and saved evidence.
- Finding reports with request/response pairs.
- Retest results using the original payloads.
- Parameter coverage report from the target analyzer.
- Session-handling validation log.
- Archived Burp project with scope and evidence.

## Pitfalls
- Scanner-reported XSS includes false positives; every finding needs manual confirmation.
- Collaborator payloads in production can fire in real admins' browsers; prefer staging.
- Burp's default payloads are noisy; tune them to avoid triggering WAF blocks that hide results.
- Forgetting to restrict scope risks testing out-of-scope hosts through the proxy.
- Session handling rules misconfigured in Burp invalidate authenticated testing; verify login state.
- Scanning with default throttle can DoS fragile apps; tune request rates.
- Forgetting to back up the Burp project loses retest evidence; archive it.
- Burp Collaborator interactions need correlation discipline; stray callbacks cause false alarms.

## References
- PortSwigger Web Security Academy: cross-site scripting.
- Burp Suite official documentation.
- OWASP XSS Prevention Cheat Sheet.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
