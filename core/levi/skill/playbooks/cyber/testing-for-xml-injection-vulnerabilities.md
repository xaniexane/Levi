---
skill_id: cyber_testing_for_xml_injection_vulnerabilities
name: Testing for XML Injection Vulnerabilities
description: Authorized testing for XML/XPath injection in your applications, with parameterized query fixes.
risk: low
permissions: []
requires_confirmation: false
tags: [web, injection, testing]
version: 1.0.0
---
## Purpose
Where applications build XML or XPath queries from user input, attackers can alter query logic to bypass authentication or extract data. This playbook covers authorized testing of your own applications for XML and XPath injection, distinguishing it from XXE (covered separately), and the parameterized-query fixes.

## When to use
- Security testing of applications using XML storage, SOAP services, or XPath queries.
- After adding search or login features backed by XML/XPath.
- Reviewing legacy code with string-built XPath.
- Validating fixes for a reported injection finding.

## Prerequisites
- Written authorization and test accounts.
- Knowledge of which features use XPath or XML query construction.
- Proxy tooling for injecting payloads.
- Access to the query-building code for fix verification.

## Procedure
1. Identify inputs flowing into XPath expressions or XML document construction.
2. Test XPath authentication bypass with boolean payloads (`' or '1'='1`) on login and search fields.
3. Test blind XPath extraction: boolean-based and timing-based inference of document content.
4. Test XML structure injection: closing and reopening tags to alter document semantics.
5. Verify whether error messages or response differences leak query results.
6. Fix: parameterized/precompiled XPath with variable binding; never concatenate input into expressions.
7. For XML building, use proper DOM/serialization APIs with encoding, not string templates.
8. Re-test all injection variants after the fix and add regression tests.
9. Test XQuery endpoints with the same payload classes where XQuery is in use.
10. Validate the SOAPAction header; spoofing can route requests to unintended operations.
11. Check XML signature validation where signatures are supposed to guarantee integrity.

## Expected outputs
- Injection test results per input with payloads and observed behavior.
- Findings with data-extraction or auth-bypass impact.
- Fixed query code and retest evidence.
- XQuery injection test results.
- SOAPAction validation assessment.
- XML signature verification review.

## Pitfalls
- Blind XPath extraction is slow but real; do not dismiss boolean-based findings.
- Input validation alone is insufficient; parameterization is the fix.
- SOAP services often hide XPath behind WSDLs; test the actual message handling.
- XXE and XPath injection co-occur; test both where XML parsers are involved.
- SOAP action spoofing can route requests to unintended operations; validate the action header.
- Signature validation that ignores unsigned portions is a classic bypass; test it.
- XML canonicalization differences between libraries break signature checks; test the real stack.
- XPath injection in reporting and analytics features is often missed; include them in scope.

## References
- OWASP Web Security Testing Guide: XML and XPath injection.
- OWASP Cheat Sheet: injection prevention.
- PortSwigger Web Security Academy: XML external entity vs XPath injection notes.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
