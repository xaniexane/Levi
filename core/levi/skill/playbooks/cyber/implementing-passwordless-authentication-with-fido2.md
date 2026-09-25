---
skill_id: cyber_implementing_passwordless_authentication_with_fido2
name: Implementing Passwordless Authentication with FIDO2
description: Deploy FIDO2/WebAuthn passwordless authentication — authenticator selection, registration ceremonies, attestation validation, and recovery design.
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, fido2, webauthn]
version: 1.0.0
---
## Purpose

Implement origin-bound, phishing-resistant authentication with FIDO2/WebAuthn: the private key never leaves the authenticator, the signature is bound to the relying party's origin (so a phishing site gets nothing useful), and there is no shared secret to phish, spray, or breach. This playbook covers the full deployment — authenticator strategy, registration and authentication ceremonies, attestation policy, and the recovery flows that make or break real-world rollouts.

## When to use

- Achieving phishing-resistant authentication for workforce or customer-facing applications.
- Replacing passwords, SMS OTP, or push MFA that adversary-in-the-middle attacks defeat.
- Meeting AAL3 / phishing-resistant MFA requirements (NIST 800-63, federal, financial, insurance).
- Building passwordless sign-in for web applications you develop in-house.
- Evaluating passkey (synced credential) vs. device-bound security key strategies.

## Prerequisites

- Relying-party implementation: WebAuthn library/server component (e.g., SimpleWebAuthn, Duo's libraries, or platform SDKs) integrated with your identity system.
- Authenticator procurement or platform support matrix: security keys (YubiKey, Feitian) and platform authenticators (Windows Hello, Touch ID/Face ID, Android) across your user devices and browsers.
- Decision on attestation requirements: none (privacy-preserving default), indirect, or direct — and which authenticator models you trust.
- Recovery and help-desk procedures designed before rollout, not after the first lost key.
- User communication explaining what changes about sign-in and what to do when devices are lost.

## Procedure

1. **Choose the credential model per population.** Device-bound credentials (security keys, TPM-backed platform keys) give the strongest assurance and are right for privileged users and high-risk transactions. Synced passkeys (iCloud Keychain, Google Password Manager, 1Password) trade a measure of assurance for usability and recovery — appropriate for general workforce and consumers. Document which populations get which, and why.
2. **Implement the registration ceremony correctly.** Generate a challenge server-side, bind it to the user and a short expiry, and validate the attestation response: check the origin matches your RP ID, verify the signature over the authenticator data, and enforce your attestation policy (e.g., require attestation for security keys to prove hardware provenance; allow `none` for platform authenticators where privacy matters). Store credential IDs and public keys — never private keys, which you never see.
3. **Implement the authentication ceremony correctly.** Issue a fresh random challenge per attempt, verify the origin/RP ID binding, check the signature with the stored public key, and enforce the signature counter (reject reused counters as cloning indicators). Require user verification (biometric/PIN) for high-assurance flows; allow its absence only where the risk assessment supports it.
4. **Set attestation and metadata policy.** Use the FIDO Metadata Service (MDS) to validate authenticator provenance and to detect compromised or decertified models — automatically distrusting authenticator models with known vulnerabilities. Keep the MDS cache updated; stale metadata silently trusts revoked devices.
5. **Design enrollment and recovery as first-class flows.** Bootstrap registration with a verified identity proofing step (Temporary Access Pass, in-person, or existing strong MFA — never a password alone for privileged users). Require two authenticators per user where feasible (primary + backup) so a lost key is an inconvenience, not a lockout. Define the re-registration ceremony with the same rigor as initial registration.
6. **Handle the edge cases.** Plan for: shared workstations (per-user credential selection UX), mobile browsers with varying WebAuthn support (test your actual fleet), cross-device (hybrid) flows using QR + Bluetooth for devices without platform authenticators, and account recovery that cannot be socially engineered at the help desk.
7. **Monitor authentication telemetry.** Log registration and authentication events with authenticator model, attestation result, counter anomalies, and failure reasons. Alert on: attestation failures, counter regressions (possible cloning), registration spikes, and authentication attempts from unexpected origins.
8. **Phase out weaker methods.** As FIDO2 coverage grows, restrict or remove fallback to SMS/push for enrolled populations — attackers downgrade to the weakest available method. Track the percentage of authentications using phishing-resistant methods as the headline metric.

## Expected outputs

- Documented credential-model decision per user population.
- Relying-party implementation with validated registration and authentication ceremonies.
- Attestation/MDS policy with compromised-model handling.
- Enrollment, backup-authenticator, and recovery procedures.
- Authentication telemetry with cloning/anomaly alerting; weaker-method phase-out plan.

## Pitfalls

- **Skipping origin and challenge validation.** The ceremony details are the security. A relying party that doesn't verify origin binding or reuses challenges has built password-equivalent theater.
- **Recovery via the help desk with weak verification.** Lost-key recovery is the new password reset — attackers will target it. Make recovery at least as strong as registration.
- **Single authenticator per user.** One key, lost or broken, equals lockout or emergency bypass. Two credentials per user is the operational minimum.
- **Ignoring the signature counter.** The counter exists to detect cloned authenticators; implementations that store but never check it waste the protection.
- **Leaving SMS as fallback.** Every phishing-resistant deployment with an SMS fallback is an SMS-phishing deployment with extra steps. Remove or heavily gate the fallback.

## References

- WebAuthn Level 2/3 specification (W3C) — https://www.w3.org/TR/webauthn/
- FIDO Alliance: FIDO2 specifications and Metadata Service — https://fidoalliance.org/
- NIST SP 800-63B (memorized-secret and authenticator guidance) — https://csrc.nist.gov/publications/detail/sp/800-63/4/final
- MITRE ATT&CK T1110 (Brute Force) / T1078 context — phishing-resistant auth as mitigation — https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
