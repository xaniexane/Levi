---
skill_id: cyber_testing_android_intents_for_vulnerabilities
name: Testing Android Intents for Vulnerabilities
description: Authorized testing of Android exported components for intent hijacking, spoofing, and data leakage.
risk: low
permissions: []
requires_confirmation: false
tags: [mobile, android, testing]
version: 1.0.0
---
## Purpose
Exported Android components that accept intents can be abused for intent spoofing, hijacking, and unauthorized data access. This playbook covers authorized security testing of your organization's own Android apps: enumerating exported components, probing them with crafted intents, and verifying fixes. It also informs detection of malicious apps abusing intents on managed devices.

## When to use
- Security assessment of your organization's Android app before release.
- After adding new exported components or deep-link handlers.
- Investigating a malicious app's intent-abuse behavior in a lab.
- MDM policy review for intent-based data leakage risks.

## Prerequisites
- Written authorization for the target app; test builds with debuggable flags where possible.
- Test device or emulator with ADB access; drozer or objection-style tooling optional.
- The app's manifest and source (preferred) for mapping exported components.
- Threat model: which components handle sensitive data or privileged actions.

## Procedure
1. Enumerate exported activities, services, receivers, and providers from the manifest and runtime.
2. For each exported component, determine what intents it accepts and what permissions guard it.
3. Send crafted intents via ADB with missing, malformed, and oversized extras; observe crashes and behavior.
4. Test for intent spoofing: can a third-party app trigger privileged actions (e.g. payments, data export)?
5. Test for hijacking: does the app send implicit intents carrying sensitive data that a malicious app could intercept?
6. Verify deep links and custom schemes validate the host/path and require authentication where needed.
7. Confirm fixes: explicit intents, signature-level permissions on sensitive components, `android:exported=false` by default.
8. Document each finding with the component, intent, payload, and resulting behavior.
9. Test intent filters for data schemes that expose internal content providers.
10. Verify PendingIntent mutability flags on modern SDKs; mutable implicit intents are hijackable.
11. Check exported providers for path-traversal in addition to intent issues.

## Expected outputs
- Exported-component inventory with risk rating per component.
- Finding reports with reproducible ADB commands and observed behavior.
- Remediation verification evidence.
- Content-provider exposure assessment.
- PendingIntent mutability audit results.
- Provider path-traversal test results.

## Pitfalls
- Testing only with the happy path misses the point; malformed extras find the crashes.
- Implicit intents for sensitive actions are a design flaw, not just a bug.
- Some intent issues require a malicious app installed; assess real-world exploitability honestly.
- OS version differences change intent resolution; test on the versions you support.
- PendingIntents with implicit intents can be hijacked; verify mutability flags.
- Task hijacking via `taskAffinity` manipulation is a separate but related risk; check it.
- Test on the minimum supported SDK; newer OS versions change intent behavior.
- Intent-based data sharing with third-party apps needs explicit user consent flows; verify them.

## References
- Android Developers: security tips and intent documentation.
- OWASP Mobile Application Security Testing Guide (MASTG).
- MITRE ATT&CK for Mobile.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
