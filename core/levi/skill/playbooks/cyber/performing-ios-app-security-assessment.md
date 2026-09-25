---
skill_id: cyber_performing_ios_app_security_assessment
name: iOS App Security Assessment
description: Assess iOS applications for data protection and hardening gaps.
risk: low
permissions: []
requires_confirmation: false
tags: [mobile, ios, assessment]
version: 1.0.0
---
# iOS App Security Assessment

## Purpose

iOS apps handle credentials, health data, and payments behind Apple's
sandbox — but misconfigurations still leak data through backups,
keychains, and insecure transport. This playbook assesses an iOS app
you are authorized to test, covering static, dynamic, and transport-
layer checks.

## When to use

- Pre-release security review of a first- or third-party iOS app.
- Validating fixes for reported mobile findings.
- MDM/enterprise app-vetting before internal distribution.
- Incident support when a mobile app is suspected in a breach.

## Prerequisites

- Written authorization to test the app and its backend APIs.
- A test device (jailbroken for deep inspection, or a standard device
  for black-box) plus the IPA; never test on a device with personal
  data.
- Tooling: MobSF or objection/Frida for runtime inspection, an
  intercepting proxy with a trusted CA, and Xcode for build analysis.

## Procedure

1. Inventory the attack surface: extract the IPA, list URL schemes,
   universal links, app extensions, and embedded frameworks; note
   third-party SDKs and their versions.
2. Review data protection: check Data Protection API class on
   sensitive files, Keychain accessibility attributes (avoid
   kSecAttrAccessibleAlways), and that secrets are not in plist files
   or NSUserDefaults.
3. Test transport security: proxy the app's traffic and confirm TLS
   with certificate validation everywhere — flag plaintext HTTP,
   disabled ATS exceptions, and custom trust managers that accept any
   certificate.
4. Inspect runtime behavior with objection/Frida: dump the keychain,
   list NSUserDefaults, check for jailbreak detection and its
   bypassability, and monitor pasteboard and screenshot exposure of
   sensitive screens.
5. Check IPC and URL handling: test custom URL schemes and universal
   links for injection or unauthorized actions, and verify UIPasteboard
   and shared containers do not leak data to other apps.
6. Review authentication and session handling: token storage, biometric
   fallback behavior, and whether logout truly invalidates server-side
   sessions.
7. Assess binary protections: PIE, stack canaries, ARC, and whether
   debug symbols or sensitive strings (API keys, endpoints) ship in
   the release build.
8. Report with reproduction: each finding needs the exact steps, the
   affected build, and a concrete fix (e.g. "set NSFileProtectionComplete
   on the credential store").

## Expected outputs

- Findings mapped to OWASP MASVS controls with severity ratings.
- Reproduction steps and affected build versions per finding.
- A retest checklist for validating fixes.

## Pitfalls

- Testing only on a non-jailbroken device: you miss keychain and
   file-protection verification — use both profiles.
- Confusing Apple's sandbox with app security: the sandbox limits
   blast radius, it does not fix your bugs.
- Flagging every ATS exception without checking whether the exception
   domain is actually sensitive.
- Destructive testing against production backends: use staging.

## References

- OWASP Mobile Application Security Verification Standard (MASVS)
- OWASP Mobile Security Testing Guide (MSTG)
- Apple Platform Security Guide (support.apple.com)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
