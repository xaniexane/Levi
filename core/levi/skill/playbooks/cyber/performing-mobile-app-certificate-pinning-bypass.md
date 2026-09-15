---
skill_id: cyber_performing_mobile_app_certificate_pinning_bypass
name: Mobile App Certificate Pinning Assessment
description: Evaluate mobile application certificate pinning controls during authorized reviews, detect bypass attempts, and recommend hardening.
risk: low
permissions: []
requires_confirmation: false
tags: [mobile, tls, hardening]
version: 1.0.0
---
## Purpose
- This playbook covers authorized security testing and defensive analysis of certificate pinning; it does not cover evading pinning on systems you do not own or have permission to test.
- Determine whether a mobile application actually enforces certificate pinning or merely claims to, during authorized security reviews.
- Detect attacker techniques that defeat pinning so monitoring and app-hardening controls can be improved.
- Give development teams concrete, testable hardening guidance for pinning implementations.

## When to use
- During an authorized mobile application security assessment or penetration test with written scope.
- When threat intelligence indicates attackers are intercepting traffic from your organization's mobile apps.
- When validating that a pinning implementation meets policy before a high-risk app ships.
- After a suspected interception incident, to determine whether pinning was bypassed or absent.

## Prerequisites
- Written authorization covering the target application and the test environment, plus a legal review if employee devices are involved.
- A test device or emulator, a proxy tool with a trusted test root CA, and a build of the app that is approved for testing.
- Baseline knowledge of the app's expected network endpoints so anomalous connections stand out.
- Source-code or build access sufficient to confirm how pinning is implemented, not just how it behaves.

## Procedure
1. Confirm scope in writing, then install the test root CA on an isolated test device that contains no personal or production data.
2. Route the application's traffic through the proxy and observe whether pinned connections fail closed or accept the test certificate.
3. Test pinning across app updates, first-launch flows, and background sync, since pinning is often enforced inconsistently.
4. Inspect the application for common pinning weaknesses: pins that are never validated, debug builds with pinning disabled, and hardcoded pins without rotation.
5. Check whether the app detects common bypass tooling or rooted and jailbroken environments, and record how it responds.
6. Review whether sensitive endpoints add defense in depth, such as payload encryption or request signing, independent of TLS.
7. Document every finding with reproduction steps, screenshots, and the exact app version tested.
8. Recommend hardening: SPKI pinning with backup pins, pin rotation procedures, fail-closed behavior, and runtime integrity checks.
9. Advise on monitoring: log pinning-validation failures server-side as potential interception indicators.
10. Verify fixes in a retest and confirm that legitimate traffic still functions, including certificate rotation scenarios.

## Expected outputs
- An authorized assessment report stating where pinning holds, where it fails, and the business risk of each gap.
- Hardening recommendations with implementation and rotation guidance for the development team.
- A retest record confirming remediation before release.
- Monitoring recommendations for detecting pinning-bypass attempts in production.

## Pitfalls
- Testing on personal or production devices, which risks intercepting credentials outside the authorized scope.
- Declaring pinning secure after one happy-path test while background services skip validation entirely.
- Recommending pinning without a rotation plan, which turns the next certificate renewal into a self-inflicted outage.
- Relying on pinning alone without server-side anomaly detection for interception attempts.

## References
- OWASP Mobile Application Security Testing Guide on network communication testing
- OWASP Mobile Application Security Verification Standard (MASVS)
- NIST SP 800-124 Guidelines for Managing the Security of Mobile Devices
- NIST SP 800-52 Guidelines for the Selection, Configuration, and Use of TLS

