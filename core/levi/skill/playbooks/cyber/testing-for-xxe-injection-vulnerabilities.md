---
skill_id: cyber_testing_for_xxe_injection_vulnerabilities
name: Testing for XXE Injection Vulnerabilities
description: Authorized XXE testing: file disclosure, SSRF via entities, and secure parser configuration fixes.
risk: low
permissions: []
requires_confirmation: false
tags: [web, xxe, testing]
version: 1.0.0
---
## Purpose
XML External Entity injection turns XML parsers into file readers and SSRF proxies. This playbook covers authorized testing of your own applications' XML handling for XXE, including out-of-band exfiltration testing done safely, and the parser-hardening configuration that eliminates the class.

## When to use
- Security testing of applications accepting XML uploads, SOAP, SAML, or document imports.
- After adding file-import or integration features using XML.
- Reviewing parser configurations across services.
- Validating fixes for a reported XXE finding.

## Prerequisites
- Written authorization and test XML ingestion points.
- Understanding of the XML parsers and libraries in use per service.
- Out-of-band test server you control (for OOB confirmation, used carefully).
- Proxy tooling for submitting crafted XML.

## Procedure
1. Inventory XML entry points: uploads, API bodies, SOAP endpoints, SAML, RSS/doc imports.
2. Identify the parser per entry point and its default entity-handling behavior.
3. Test classic XXE: define an external entity pointing at a safe local marker and observe inclusion.
4. Test parameter entities and out-of-band exfiltration to your controlled server for blind cases.
5. Test XXE-driven SSRF: entity URLs targeting internal metadata endpoints (use harmless paths).
6. Assess billion-laughs/quadratic-blowup DoS only in staging with strict limits, or skip and note the risk.
7. Fix: disable DTDs entirely where possible; otherwise disable external entities and XInclude, and use least-privilege parsers.
8. Verify the fix per parser (configurations differ by library) and re-test every entry point.
9. Test JSON-to-XML conversion endpoints; they can introduce XXE behind a JSON facade.
10. Verify each XML parser library independently; hardening one does not cover a polyglot stack.
11. Check document-upload pipelines (Office, SVG) that parse XML internally.

## Expected outputs
- XXE test results per entry point with parser identified.
- Findings with file-read or SSRF impact evidence.
- Hardened parser configurations and retest evidence.
- JSON-to-XML conversion assessment.
- Per-library parser hardening matrix.
- Document-pipeline XML parsing review.

## Pitfalls
- Each XML library has different hardening flags; a fix for one parser does not cover the others.
- Disabling DTDs can break legitimate document features; test functionality after hardening.
- OOB testing against internal metadata endpoints must stay harmless; never exfiltrate real credentials.
- SAML and SOAP libraries have their own XXE histories; check their specific guidance.
- DTD disabling in one parser library does not cover others in a polyglot stack.
- Office and SVG documents contain XML; upload pipelines parse them implicitly.
- Error messages from parsers can leak file existence; standardize error handling.
- XXE in document-to-PDF or rendering services runs with service privileges; assess the blast radius.

## References
- OWASP Top 10: XML External Entities (owasp.org/www-project-top-ten).
- OWASP Cheat Sheet: XXE prevention.
- PortSwigger Web Security Academy: XXE injection.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
