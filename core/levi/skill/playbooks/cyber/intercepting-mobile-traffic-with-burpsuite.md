---
skill_id: cyber_intercepting_mobile_traffic_with_burpsuite
name: Intercepting Mobile Traffic with Burp Suite (Authorized Testing)
description: Configure Burp Suite interception for security testing of your own mobile applications.
risk: low
permissions: []
requires_confirmation: false
tags: [appsec, mobile-security, testing]
version: 1.0.0
---
## Purpose
This playbook covers setting up Burp Suite as an intercepting proxy for authorized security testing of mobile applications your organization owns or has written permission to test. It is strictly a defensive testing workflow: find flaws in your own apps before attackers do. Never intercept traffic of apps or users you are not authorized to test.

## When to use
- Security-testing your organization's iOS/Android app for API flaws, insecure transport, or data leakage.
- Validating that certificate pinning and transport security actually work.
- Reproducing a reported mobile vulnerability in a controlled lab.

## Prerequisites
- Written authorization to test the specific application and backend.
- A lab device (or emulator) you own, with the ability to install a CA certificate.
- Burp Suite (Community or Professional) and a test backend environment, not production user data.

## Procedure
1. **Confirm scope in writing.** Record the app version, backend endpoints, test accounts, and testing window; intercepting anything outside this scope is out of bounds.
2. **Install the Burp CA on the lab device.** Export Burp's CA certificate and install it in the device trust store (system store on rooted Android, or via profile on iOS lab devices).
3. **Route traffic through Burp.** Configure the device Wi-Fi proxy (or use invisible proxying) to send app traffic to Burp; verify interception with a simple request.
4. **Handle certificate pinning.** For your own app, use a debuggable build with pinning disabled, or bypass pinning in the lab with documented tooling — never ship the bypass.
5. **Map and test methodically.** Build the site map, then test for: cleartext or weak TLS, sensitive data in URLs/logs, broken authentication, insecure direct object references, and excessive data exposure in API responses.
6. **Document findings with evidence.** Record requests/responses proving each issue, the affected app version, and remediation guidance; file through the normal vuln workflow.
7. **Clean up.** Remove the Burp CA from the device, revoke test accounts, and confirm no test data remains in production systems.

8. **Verify pinning in release builds.** Confirm certificate pinning is active in the production build, not just documented; test with a proxy to prove it.
9. **Check backend authorization.** Most mobile findings are really API findings; test every endpoint for BOLA and broken function-level authorization with different privilege tokens.

## Expected outputs
- Scoped test plan with authorization record.
- Burp project with mapped attack surface and documented findings.
- Remediation tickets with evidence and retest results.
- Example: intercepted traffic reveals the app sends the session token in a URL parameter over a pinned connection; the finding includes the request proving token leakage into logs and proxies.

## Pitfalls
- Testing production backends with active scanning: you can corrupt data or trigger fraud controls.
- Leaving the Burp CA installed on a device that later handles real credentials.
- Confusing "traffic is encrypted" with "traffic is secure": inspect what the API actually exposes.

- Testing with a rooted or jailbroken device and declaring the app secure; real attackers work with those devices, so test both configurations.
- Intercepting traffic that includes other users' data during shared-backend testing; scope test accounts to synthetic data only.

## References
- OWASP Mobile Application Security Testing Guide (mas.owasp.org/MASTG).
- PortSwigger Burp Suite documentation (portswigger.net/burp/documentation).
- OWASP MASVS (mas.owasp.org/MASVS) — verification standard for mobile apps.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
