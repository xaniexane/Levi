---
skill_id: cyber_performing_soap_web_service_security_testing
name: SOAP Web Service Security Testing
description: Test SOAP web services for injection, authentication, and XML-specific flaws during authorized assessments.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, soap, testing]
version: 1.0.0
---

## Purpose
- This playbook covers authorized security testing of SOAP services to find and fix flaws; it does not cover attacking services without permission.
- Find the vulnerabilities SOAP services commonly carry: XXE, XML injection, weak WS-Security, and broken authentication.
- Test the XML-specific attack surface that REST-focused scanners miss.
- Give development teams remediation guidance for legacy SOAP stacks.

## When to use
- During authorized application penetration tests where SOAP services are in scope.
- When legacy SOAP services are exposed to partners or the internet.
- During secure code reviews of services that parse untrusted XML.
- When validating WS-Security implementations before go-live.

## Prerequisites
- Written authorization with the target services and test accounts defined.
- WSDL files and documentation for the services under test.
- A test environment with representative data and verbose error handling enabled for diagnosis.
- Intercepting proxy tooling and XML-aware testing tools.

## Procedure
1. Confirm authorization and scope, then collect WSDLs and map all operations, parameters, and data types.
2. Review authentication and session handling: how clients authenticate and whether operations enforce authorization.
3. Test for XML external entity injection with safe out-of-band payloads in a controlled environment.
4. Test for XPath and XQuery injection in operations that query XML data stores.
5. Attempt oversized and deeply nested XML payloads to check for denial-of-service protections.
6. Review WS-Security configuration: signature and encryption coverage, timestamp freshness, and replay protection.
7. Test for business-logic flaws: parameter tampering, enumeration, and workflow bypass within operations.
8. Check error handling for stack traces and internal details that aid attackers.
9. Verify transport security: TLS versions, certificate validation, and mutual TLS where required.
10. Document each finding with the operation, payload, response evidence, and severity.
11. Provide remediation: disable DTD processing, use parameterized queries, enforce schema validation, and harden WS-Security.
12. Retest after fixes in the same environment.

## Expected outputs
- Test findings with operation-level evidence and severity ratings.
- Remediation guidance specific to the SOAP stack in use.
- Retest results confirming fixes.
- A regression test pack of the payloads used, for rerunning after fixes.
- Developer training on XML security for teams maintaining SOAP services.

## Pitfalls
- Testing XXE with payloads that exfiltrate real data; keep entity tests harmless and local.
- Relying on WSDL alone; hidden operations and version differences are common.
- Assuming transport security fixes message-level flaws; test both layers.
- Assuming input validation at the XML schema level stops injection; validate at the sink too.

## References
- OWASP Testing Guide v5 on web service testing
- OWASP Web Service Security Testing guidance
- OWASP XML External Entity Prevention Cheat Sheet
- CWE-611 on XXE vulnerabilities
- OASIS WS-Security specifications
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
