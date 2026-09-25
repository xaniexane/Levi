---
skill_id: cyber_testing_mobile_api_authentication
name: Testing Mobile API Authentication
description: Authorized testing of mobile app API authentication: token storage, pinning, and session handling.
risk: low
permissions: []
requires_confirmation: false
tags: [mobile, api, authentication]
version: 1.0.0
---
## Purpose
Mobile apps authenticate to the same APIs as web clients but add mobile-specific risks: insecure token storage, missing certificate pinning, and weak biometric fallbacks. This playbook covers authorized testing of your organization's own mobile apps and their backend authentication.

## When to use
- Security assessment of a mobile app release.
- After changing mobile auth flows (biometric login, SSO, token refresh).
- Investigating suspected mobile session hijacking.
- MDM/BYOD policy review for app authentication requirements.

## Prerequisites
- Written authorization; test builds and test accounts.
- Test device (rooted/jailbroken lab device or emulator) with proxy tooling.
- Understanding of the app's auth flow: OAuth, tokens, biometrics, device binding.
- Backend log access for correlating test activity.

## Procedure
1. Map the mobile auth flow: login, token issuance, storage, refresh, and logout.
2. Inspect token storage on the device: keychain/keystore vs plaintext files or preferences.
3. Test certificate pinning by proxying TLS; verify the app rejects your proxy CA (in the lab build).
4. Test session handling: token expiry, refresh rotation, logout revocation, and concurrent-session behavior.
5. Test biometric authentication: fallback strength, bypass via OS settings, and server-side enforcement.
6. Attempt token extraction and replay from the device backup or filesystem to another device.
7. Verify jailbreak/root detection exists but is treated as defense-in-depth, not the primary control.
8. Confirm server-side enforcement of every client-side check before closing findings.
9. Test app attestation (Play Integrity, App Attest) enrollment and server-side enforcement.
10. Verify that attestation failures fail closed rather than falling back to weaker checks.
11. Check certificate transparency expectations for pinned backend certificates.

## Expected outputs
- Mobile auth test report with device-level evidence.
- Token storage and transport findings.
- Backend enforcement verification results.
- App attestation test results with enforcement mode.
- Attestation failure-mode verification.
- Backend certificate pinning review.

## Pitfalls
- Pinning in the lab build may differ from the store build; verify the release configuration.
- Client-side checks (root detection, obfuscation) slow attackers but do not replace server validation.
- Backups and screenshots can leak tokens; test the backup path explicitly.
- Deep links carrying tokens are a common mobile-specific leak.
- Emulator detection is bypassable; treat it as a signal, not a gate.
- Attestation that fails open is worse than none; it creates false confidence.
- Older app versions without new auth controls must be force-upgraded or blocked.
- Push notification tokens can be abused for spam or phishing; protect their registration endpoints.

## References
- OWASP Mobile Application Security Testing Guide (MASTG).
- OWASP MASVS (Mobile Application Security Verification Standard).
- NIST SP 800-63B, Digital Identity Guidelines.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
