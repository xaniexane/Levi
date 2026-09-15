---
skill_id: cyber_reverse_engineering_ios_app_with_frida
name: Analyzing iOS Malware with Frida
description: Dynamically analyze suspicious iOS apps with Frida in a lab: hook APIs, trace network and keychain access.
risk: info
permissions: []
requires_confirmation: false
tags: [malware, ios, dynamic-analysis]
version: 1.0.0
---
## Purpose
Frida's dynamic instrumentation lets analysts observe what an iOS app actually does at runtime: network calls, keychain access, and anti-analysis behavior. This playbook covers lab-based dynamic analysis of suspicious iOS apps or iOS malware samples using a test device that you own. It does not cover bypassing App Store protections on devices you do not own or analyzing apps without authorization.

## When to use
- A suspicious iOS app is reported (sideloaded enterprise app, malicious profile payload).
- Validating static-analysis suspicions about an iOS sample's runtime behavior.
- Security assessment of your organization's own iOS app (with authorization).
- Incident response involving a potentially compromised iOS device fleet.

## Prerequisites
- A lab-owned test device (jailbroken) or iOS research environment; Frida server deployed.
- Frida client tooling on the analysis workstation and basic Frida scripting knowledge.
- The target IPA/app installed on the test device; sample hash recorded.
- Isolated network with traffic capture for correlating observed behavior.

## Procedure
1. Prepare the lab device: snapshot state, install the target app, and start Frida server.
2. Attach Frida to the app process and enumerate loaded classes and methods of interest.
3. Hook networking APIs (NSURLSession, CFNetwork) to log destinations, headers, and payloads.
4. Hook keychain and data-protection APIs to observe credential and secret storage behavior.
5. Hook anti-analysis checks (jailbreak detection, debugger checks) to understand evasion logic.
6. Exercise the app's features while tracing; capture traffic for C2 and exfiltration analysis.
7. Correlate observed API calls with static findings to confirm malicious capabilities.
8. Extract IOCs and document behavior with Frida scripts archived for reproducibility.
9. Snapshot the device filesystem before and after runs to catch dropped files.
10. Hook URL scheme and universal-link handlers to map the app's external attack surface.
11. Record the exact iOS and Frida versions; hooking reliability varies by release.

## Expected outputs
- Frida scripts used, with logged API traces and network captures.
- Behavioral findings: C2, exfiltration, persistence, and evasion techniques.
- IOC list and MDM/policy recommendations.
- Filesystem diff showing files created by the app.
- URL-scheme and link-handler attack-surface map.
- Environment version record for reproducibility.

## Pitfalls
- Jailbreak detection may alter behavior; instrument the checks themselves to see both paths.
- Certificate pinning blocks traffic inspection; only bypass it on lab devices you own.
- iOS version differences change private API behavior; record exact OS and Frida versions.
- Dynamic analysis sees only executed paths; combine with static review for coverage.
- iOS 16+ lockdown mode and pointer authentication change hooking reliability; pin tool versions.
- App Store apps cannot be instrumented on non-jailbroken devices; plan the lab accordingly.
- Background app refresh can trigger behavior outside your tracing window; monitor continuously.
- Enterprise certificate abuse is a distribution vector; monitor for unexpected enterprise-signed apps.

## References
- Frida documentation (frida.re/docs).
- Apple Platform Security documentation.
- MITRE ATT&CK for Mobile.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
