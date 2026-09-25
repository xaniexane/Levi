---
skill_id: cyber_implementing_jwt_signing_and_verification
name: Implementing JWT Signing and Verification
description: Harden JSON Web Token issuance and validation — strong signing algorithms, key management, claim validation, and safe library configuration.
risk: info
permissions: []
requires_confirmation: false
tags: [application-security, authentication, cryptography]
version: 1.0.0
---
## Purpose

Make JWTs a trustworthy authentication mechanism instead of the vulnerability. This playbook covers secure token issuance (algorithm choice, key strength, claim design) and bulletproof verification (signature enforcement, algorithm whitelisting, claim checks, key rotation) so that classic JWT attacks — `alg:none`, algorithm confusion, weak HMAC secrets, missing claim validation — are structurally impossible rather than hopefully avoided.

## When to use

- Designing authentication for APIs, SPAs, or microservices that will use JWTs.
- Auditing an existing JWT implementation after a penetration test or incident.
- Migrating from opaque session tokens to JWTs (or deciding whether you should at all).
- Reviewing third-party libraries and identity providers' token configurations.
- Meeting requirements for token integrity in regulated applications.

## Prerequisites

- Inventory of where JWTs are issued, verified, and consumed across your services.
- A secrets/KMS solution for signing keys (never hardcode secrets in code or config files).
- Understanding of your threat model: which attackers, what token theft or forgery would enable.
- Test environment where you can exercise negative cases (tampered tokens, wrong algorithms, expired tokens).
- Library documentation for your JWT stack — secure defaults vary wildly between libraries.

## Procedure

1. **Choose the algorithm deliberately.** Prefer asymmetric signing (RS256/ES256 or EdDSA) so verifiers hold only the public key — a compromised API server then cannot mint tokens. Use HS256 only when issuer and verifier are the same trusted service, with a 256-bit random secret from a CSPRNG. Never accept `none`, and never let the token's `alg` header select the algorithm.
2. **Pin the expected algorithm in every verifier.** Configure each verification call with an explicit allowlist (e.g., `algorithms=["RS256"]`). Algorithm-confusion attacks (RS256→HS256, using the public key as an HMAC secret) succeed only when verifiers are algorithm-agile. This single setting defeats the two most famous JWT attack classes.
3. **Manage keys like production secrets.** Generate with a CSPRNG, store in a KMS or secrets manager, rotate on a schedule (e.g., 90 days) with overlapping validity, and publish verification keys via JWKS with `kid` headers so rotation does not break verifiers. Never commit keys to repositories — scan for them with gitleaks as a backstop.
4. **Validate every security-relevant claim.** On verification, check `exp` (with small clock-skew leeway, e.g., ±60s), `nbf`, `iss` against an allowlist, `aud` matching the receiving service, and `sub` format. Reject tokens with missing or unexpected claims rather than defaulting to permissive. Validate `jti` uniqueness for single-use or high-value tokens.
5. **Keep tokens short-lived and narrow.** Access tokens: minutes (5–15), not hours. Encode only the claims the resource server needs — never PII, permissions snapshots that go stale, or anything sensitive, since payloads are merely base64, not encrypted. Use refresh tokens (rotated, bound, revocable) for session continuity.
6. **Decide JWT vs. opaque tokens honestly.** If you need instant revocation, per-session metadata, or your verifiers already call a central service, opaque reference tokens with a lookup are simpler and safer. Use JWTs where stateless verification across trust boundaries genuinely pays for the complexity.
7. **Harden transport and storage.** JWTs travel only over TLS; cookies carrying them get `Secure`, `HttpOnly`, and `SameSite` flags. For SPAs, weigh the XSS exposure of localStorage against the CSRF exposure of cookies — there is no option with zero trade-offs, so document the choice.
8. **Test the negative cases.** Build a verification test suite: tampered signature, `alg:none`, algorithm swapped, expired, wrong issuer/audience, missing `kid`, oversized tokens, and key-confusion payloads. Run it in CI. Re-run after every library upgrade.

## Expected outputs

- Documented token design: algorithm, key management, claim schema, lifetimes.
- Verifier configurations with pinned algorithms and full claim validation, covered by negative test suites.
- Key rotation procedure with JWKS publication and overlap handling.
- Decision record on JWT vs. opaque tokens per use case.
- Secret-scanning coverage for signing keys in CI.

## Pitfalls

- **Trusting the `alg` header.** The single most exploited JWT flaw. The verifier — not the token — decides which algorithms are acceptable.
- **Weak HS256 secrets.** Human-memorable secrets fall to offline brute force in minutes with hashcat. 256 bits from a CSPRNG or don't use HMAC.
- **Skipping `aud`/`iss` checks.** A token minted for service A accepted by service B is a cross-service impersonation primitive.
- **Long-lived access tokens.** An hour-long token is an hour-long session that cannot be revoked. Short lifetimes plus rotation beat revocation lists for scale.
- **Putting authorization data in tokens and never refreshing it.** Role changes, terminations, and permission revocations do not propagate to outstanding JWTs. Keep lifetimes short or check a revocation/status endpoint for sensitive actions.

## References

- RFC 7519 (JSON Web Token), RFC 7515 (JWS), RFC 7517 (JWK) — https://www.rfc-editor.org/
- OWASP JWT Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- MITRE ATT&CK T1606 (Forge Web Credentials) — https://attack.mitre.org/techniques/T1606/
- NIST SP 800-63B guidance on session and token management — https://csrc.nist.gov/publications/detail/sp/800-63/4/final
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
