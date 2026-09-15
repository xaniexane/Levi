---
skill_id: cyber_implementing_digital_signatures_with_ed25519
name: Digital Signatures with Ed25519
description: Implement Ed25519 digital signatures for authentication, integrity, and non-repudiation.
risk: low
permissions: []
requires_confirmation: false
tags: [cryptography, signing]
version: 1.0.0
---
## Purpose
Ed25519 is the modern default for digital signatures: fast, small signatures and keys, deterministic
(no RNG failures like ECDSA), and resistant to common implementation pitfalls. It's the right choice
for signing artifacts, tokens, API requests, and firmware — anywhere authenticity and integrity
matter. This playbook implements Ed25519 correctly: key generation, secure storage,
signing/verification workflows, and rotation.

## When to use
- Adding authenticity to artifacts, messages, API requests, or software updates.
- Replacing RSA/ECDSA signatures with a safer, faster modern primitive.
- Building signed-token schemes (beyond JWT defaults) or request-signing for service auth.
- Meeting integrity and non-repudiation requirements with minimal cryptographic risk.
- Anywhere "we need signatures" is the requirement and the algorithm choice is yours.

## Prerequisites
- A vetted Ed25519 implementation: libsodium, or the standard library of your platform (never
  hand-rolled crypto).
- Key-management decision: HSM/KMS for high-value signing keys, OS keychain or vault for operational
  keys.
- Defined what is signed: the exact byte format (canonicalization!) — signatures over ambiguous
  encodings are broken signatures.
- Verification points identified: every consumer that must verify, with trust-anchor distribution
  planned.
- A rotation and compromise-response plan written before keys are generated.

## Procedure
1. **Choose the primitive deliberately.** Use Ed25519 (EdDSA over Curve25519) for new signatures.
   Prefer Ed25519ctx or Ed25519ph variants only when domain separation or pre-hashing is
   specifically needed — plain Ed25519 fits most cases. Document why Ed25519 (deterministic,
   side-channel-resistant design, small keys).
2. **Generate keys securely.** Generate with the vetted library's keygen (libsodium
   crypto_sign_keypair or equivalent) on the machine/HSM where the private key will live — never
   transmit private keys. Verify keygen used the OS CSPRNG. For high-value keys, generate in an HSM
   or KMS and never export.
3. **Define the signed message format precisely.** Specify canonical byte encoding before signing
   (e.g., fixed field order, length-prefixing, or a canonical JSON profile). Ambiguous serialization
   enables signature confusion and cross-protocol attacks — the format spec is part of the security
   design.
4. **Implement signing with context separation.** Include a domain-separation string (protocol name,
   purpose, version) in the signed payload. This prevents a signature valid in one context (test
   token) from being replayed in another (production auth). Verify implementations reject
   wrong-context signatures in tests.
5. **Implement verification strictly.** Verifiers must: use constant-time comparison (the library
   handles it — don't compare manually), check the full signature (no truncation), validate the
   signer's public key against the trust store (not from the message itself), and fail closed on any
   error. Test with tampered messages, wrong keys, and truncated signatures — all must fail.
6. **Distribute trust anchors securely.** Public keys reach verifiers via: pinned in the
   application, fetched over authenticated channels, or via a PKI/certificate. Never accept a public
   key from the same unauthenticated channel as the signed data — that's trusting the attacker to
   identify themselves.
7. **Protect private keys.** High-value: HSM/KMS with usage logging and no export. Operational: OS
   keychain or secrets manager with restricted ACLs, never in code repos or config files. Alert on
   unexpected signing operations — signing-key use is a high-signal event.
8. **Plan rotation and revocation.** Rotate signing keys on schedule (annually or per policy);
   support key versioning so verifiers accept N and N+1 during transition. On suspected compromise:
   revoke the key, notify verifiers, rotate immediately, and investigate what was signed with the
   compromised key (non-repudiation cuts both ways).
9. **Test the cryptographic properties.** Verify: signatures from one key don't verify under
   another, modified messages fail, signatures are deterministic for the same message (Ed25519
   property — useful for testing), and cross-context replays fail. Include these in the test suite
   permanently.
10. **Document the scheme.** Write the spec: algorithm, library and version, key formats, message
    canonicalization, context strings, trust-anchor distribution, rotation schedule, and compromise
    procedure. Future maintainers (and auditors) need this to avoid "improving" the crypto into
    breakage.

## Expected outputs
- Ed25519 signing/verification implemented with a vetted library, canonical message formats, and
  context separation.
- Keys generated and stored per value tier (HSM/KMS for high-value), with usage monitoring.
- Trust-anchor distribution to all verifiers via authenticated channels.
- Rotation, revocation, and compromise-response procedures documented and tested.
- A written cryptographic scheme spec and property tests in the suite.

## Pitfalls
- Hand-rolled or obscure implementations: use libsodium or platform standard libraries. Custom
  Ed25519 code is where vulnerabilities live.
- Ambiguous message encoding: signing JSON with non-canonical serialization lets attackers reorder
  fields while keeping a valid signature. Canonicalize.
- Missing context separation: signatures replayed across protocols or environments. Domain-separate
  everything.
- Private keys in repos/configs: the most common real-world failure — keys must live in
  HSM/KMS/keychain, never in code.
- No rotation plan: the first suspected compromise becomes a crisis. Key versioning and rotation
  procedures must exist before they're needed.

## References
- RFC 8032 (Edwards-Curve Digital Signature Algorithm, EdDSA)
- libsodium documentation (crypto_sign API, key generation, best practices)
- NIST FIPS 186-5 (EdDSA as an approved signature scheme)
- "Serious Cryptography" (Aumasson) — practical Ed25519 guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
