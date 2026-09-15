---
skill_id: cyber_performing_thick_client_application_penetration_test
name: Thick Client Application Penetration Test
description: Assess thick client applications for local data exposure, insecure communications, and logic flaws during authorized tests.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, thick-client, testing]
version: 1.0.0
---

## Purpose
- This playbook covers authorized security testing of thick client applications to find and fix flaws.
- Find the vulnerabilities thick clients commonly carry: local data stores, hardcoded secrets, and weak update mechanisms.
- Test the client-server protocol for authentication, authorization, and injection flaws.
- Give development teams platform-specific remediation guidance.

## When to use
- During authorized application penetration tests where thick clients are in scope.
- Before major releases of desktop or rich-client applications.
- When thick clients handle sensitive data or privileged operations.
- After incidents involving client-side tampering or data theft.

## Prerequisites
- Written authorization with the application, version, and test environment defined.
- Test builds, test accounts, and ideally debug symbols or source access.
- An isolated lab with proxy tooling, debuggers, and decompilers as appropriate to the platform.
- Understanding of the application's architecture: local storage, network protocols, and update mechanisms.

## Procedure
1. Confirm authorization and install the application in the isolated lab.
2. Map the attack surface: local files, registry or config stores, network endpoints, and IPC mechanisms.
3. Inspect local storage for sensitive data: credentials, tokens, PII, and encryption keys at rest.
4. Decompile or disassemble the client to find hardcoded secrets, API keys, and disabled security checks.
5. Intercept client-server traffic with a proxy; check for TLS, certificate validation, and sensitive data in transit.
6. Test authentication and session handling: token storage, timeout, and resistance to replay.
7. Test authorization: manipulate client-side controls and requests to access other users' data or privileged functions.
8. Probe for injection in every input the client sends to the server.
9. Review the update mechanism: signature verification, transport security, and downgrade protection.
10. Check for anti-tampering effectiveness without relying on it as a primary control.
11. Document findings with reproduction steps, screenshots, and affected versions.
12. Provide remediation per finding and retest after fixes.

## Expected outputs
- A penetration test report with findings, evidence, and severity ratings.
- Platform-specific remediation guidance.
- Retest results confirming fixes.
- A thick-client testing checklist reusable across applications.
- Secure defaults documentation for the client platform.

## Pitfalls
- Testing only the network layer; thick client flaws live in local storage and binary logic too.
- Relying on obfuscation as a finding mitigant; it slows attackers but fixes nothing.
- Breaking the test environment with aggressive fuzzing; snapshot and restore between test phases.
- Testing with an admin account only; also test with the least-privileged user role.

## References
- OWASP Application Security Verification Standard for test criteria
- OWASP Web Security Testing Guide for client-server testing patterns
- OWASP Mobile Security Testing Guide for analogous rich-client techniques
- CWE entries for client-side vulnerabilities
- Platform documentation for the application's framework
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
