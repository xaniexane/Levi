---
skill_id: cyber_performing_cryptographic_audit_of_application
name: Cryptographic Audit of Applications
description: Audit application cryptography for algorithm choice, key management, and implementation flaws.
risk: info
permissions: []
requires_confirmation: false
tags: [cryptography, assessment, appsec]
version: 1.0.0
---

## Purpose

Applications fail at cryptography far more often through misuse than through broken ciphers: hard-coded keys, ECB mode, MD5 password hashes, disabled certificate validation, and homegrown protocols. A cryptographic audit systematically reviews how an application uses crypto — algorithms, modes, key lifecycle, randomness, and transport security — against current standards, producing prioritized findings developers can fix. This is a defensive design and code review discipline.

## When to use

- Security review of an application that encrypts data, handles credentials, or signs tokens.
- Pre-release gate for features involving new cryptographic implementations.
- Responding to a crypto-related finding from a penetration test or scanner.
- Evaluating a vendor's cryptographic claims during procurement.
- Planning migration off deprecated algorithms (SHA-1, 3DES, RSA-1024, TLS 1.0/1.1).

## Prerequisites

- Access to source code, cryptographic library versions, and configuration (cipher suites, protocol versions).
- Threat model: what data is protected, from whom, and for how long (retention horizon drives algorithm strength requirements).
- Current standards baseline: NIST SP 800-131A transitions, BSI TR-02102, or your organization's crypto policy.
- Tooling: static analysis for crypto misuse (e.g., Semgrep crypto rules), TLS scanners (testssl.sh, sslyze), and dependency scanners for known-weak library versions.
- Developer time: findings without fix ownership become permanent backlog.

## Procedure

1. **Inventory cryptographic usage.** Map every place the application encrypts, hashes, signs, generates randomness, or validates certificates: data-at-rest encryption, password storage, session tokens, API signatures, license checks, and TLS configuration. An incomplete inventory invalidates the audit.
2. **Review algorithm and parameter choices.** Flag deprecated or weak primitives: MD5/SHA-1 for security purposes, DES/3DES, RC4, RSA < 2048, ECC < 224-bit, ECB mode, CBC without integrity, and static IVs. Verify key lengths and iteration counts (password hashing: Argon2id/bcrypt/scrypt with tuned work factors, never fast hashes).
3. **Audit key management.** Trace key lifecycle: generation (CSPRNG?), storage (HSM/KMS/vault vs. config files and source code), distribution, rotation policy and history, and destruction. Hard-coded keys and keys committed to repositories are critical findings; unrotated long-lived keys are high.
4. **Check randomness.** Verify all security-sensitive randomness (keys, IVs, nonces, tokens) comes from the OS CSPRNG (`getrandom`, `BCryptGenRandom`, `crypto.randomBytes`) — never `Math.random`, `rand()`, or time-seeded PRNGs. Nonce/IV reuse across messages is a finding even with a strong cipher.
5. **Review protocol usage.** Scan TLS endpoints with testssl.sh/sslyze: protocol versions (TLS 1.2+ only), cipher suite ordering (AEAD preferred, no export/anonymous/null), certificate validation (no disabled checks, proper hostname verification), and HSTS. Review custom protocol designs with extra skepticism — "homegrown crypto protocol" is itself a finding.
6. **Examine implementation pitfalls.** Look for: padding oracle exposure (distinguishable error messages), timing side channels in comparisons (non-constant-time MAC/token checks), IV/nonce misuse, and key/IV confusion. These are code-level findings requiring targeted review, not scanner output.
7. **Prioritize and report.** Rank findings by exploitability and data impact: key disclosure and broken transport crypto first, weak-but-not-yet-broken algorithms as migration backlog. Each finding needs: location, the weakness, why it matters, and the concrete fix (algorithm, library call, configuration).
8. **Verify remediation.** Re-run scanners and targeted code review against the fixed build; cryptographic fixes are easy to get subtly wrong (e.g., adding a MAC but not verifying it). Confirm with tests, not just code inspection.

## Expected outputs

- A complete cryptographic inventory: algorithms, keys, randomness sources, and TLS configurations.
- Prioritized findings with locations, impact reasoning, and concrete fixes.
- Key-management assessment: lifecycle gaps, storage weaknesses, rotation status.
- TLS scan results and required configuration changes.
- Verification evidence that fixes are correctly implemented.

## Pitfalls

- Auditing algorithms while ignoring key management — the strongest cipher with a hard-coded key is theater.
- Treating "uses AES" as sufficient without checking mode, IV handling, and integrity.
- Missing client-side or mobile-app crypto; audit every platform the application ships.
- Accepting "we'll migrate later" for deprecated algorithms without a dated plan — deprecation windows close.
- Verifying fixes by reading the diff instead of re-testing; crypto bugs hide in details the diff does not show.

## References

- NIST SP 800-131A, "Transitions: Recommendation for Transitioning the Use of Cryptographic Algorithms and Key Lengths"
- NIST SP 800-57, "Recommendation for Key Management"
- OWASP Cryptographic Storage Cheat Sheet
- BSI TR-02102, "Cryptographic Mechanisms: Recommendations and Key Lengths"
- IETF RFC 8446 (TLS 1.3) for transport security baseline
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
