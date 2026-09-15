---
skill_id: cyber_conducting_mobile_app_penetration_test
name: Conducting Authorized Mobile App Penetration Tests
description: Practitioner guide to planning and executing authorized security assessments of iOS and Android applications.
risk: info
permissions: []
requires_confirmation: false
tags: [mobile, assessment, pentest]
version: 1.0.0
---
## Purpose
Mobile apps handle sensitive data on untrusted devices, making insecure storage, weak transport, and broken authentication common findings. This playbook structures an authorized mobile assessment: scoping, static and dynamic analysis, backend API testing, and reporting -- covering both the app binary and its server-side components.

## When to use
- Assessing a mobile app before release or major update.
- Meeting compliance requirements for mobile application testing.
- Investigating a mobile-related security incident.
- Validating fixes from a previous assessment.

## Prerequisites
- Written authorization covering the app, backend APIs, and test accounts.
- Test devices (physical or emulated) for iOS and Android as applicable.
- App binaries and, ideally, debug builds or source access.
- Backend scope defined: which APIs and environments may be tested.

## Procedure
1. Confirm scope and authorization. Document the app versions, platforms, backend endpoints, and prohibited actions; get sign-off.
2. Perform static analysis. Examine the binary for hardcoded secrets, insecure configurations, debug flags, and weak cryptography.
3. Assess data storage. Check local databases, preferences, keychains/keystores, caches, and backups for sensitive data at rest.
4. Test transport security. Intercept traffic with a proxy to verify TLS, certificate validation, and pinning behavior; check for sensitive data in transit.
5. Test authentication and session handling. Evaluate login flows, token storage and expiry, biometric bypass resistance, and session invalidation.
6. Test the backend APIs. Apply API security testing methodology to the app's endpoints, focusing on authorization flaws.
7. Review platform-specific risks. Check for jailbreak/root detection, code tampering protections, and proper use of platform security APIs.
8. Report and retest. Document findings with evidence and remediation guidance; verify fixes, especially around data storage and transport.

## Expected outputs
- Assessment report with evidenced mobile-specific findings.
- Backend API findings integrated with the mobile report.
- Retest confirmation.

## Pitfalls
- Testing only the app while ignoring the backend API misses the highest-impact flaws.
- Intercepting traffic without proper certificate setup leads to false conclusions.
- Production backend testing risks real user data; prefer staging environments.
- Debug builds behave differently from release builds; test what ships.

## References
- OWASP Mobile Application Security Testing Guide (MASTG)
- OWASP Mobile Top 10
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
