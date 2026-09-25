---
skill_id: cyber_performing_jwt_none_algorithm_attack
name: JWT none-Algorithm Attack Defense
description: Detect and eliminate JWT algorithm-confusion and none-algorithm flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [web, authentication, hardening]
version: 1.0.0
---
# JWT none-Algorithm Attack Defense

## Purpose

JWT libraries that honor the token's self-declared `alg` header can be
tricked: an attacker swaps RS256 for HS256 (using the public key as the
HMAC secret) or for `none` (no signature at all) and forges tokens. This
defensive playbook covers detecting such attacks and hardening token
validation so algorithm confusion is impossible.

## When to use

- Hardening any service that validates JWTs.
- Reviewing authentication code during a security assessment.
- Investigating suspicious authenticated sessions with anomalous
  token characteristics.
- Validating JWT library configuration after upgrades.

## Prerequisites

- Access to the token-validation code and configuration for each
  service, plus authentication logs showing token headers or
  validation failures.
- Knowledge of which algorithms each service legitimately uses
  (usually exactly one).
- A test environment for sending crafted tokens.

## Procedure

1. Pin the algorithm explicitly: validation must specify the expected
   algorithm (e.g. allow only RS256) and reject anything else —
   never let the token's `alg` header choose.
2. Reject `alg: none` unconditionally: no code path, fallback, or
   legacy compatibility mode should accept unsigned tokens.
3. Separate keys by algorithm: never use the same key material for
   HMAC and RSA operations; an RS256 public key must never be usable
   as an HS256 secret.
4. Verify signature before claims: check the signature first, then
   validate `exp`, `nbf`, `aud`, and `iss` — and fail closed on any
   missing or unexpected claim.
5. Audit library configuration: confirm the JWT library version is
   current and that its defaults do not permit algorithm confusion;
   several historic CVEs trace to permissive defaults.
6. Detect attacks in logs: alert on tokens arriving with `alg: none`
   or with an algorithm different from the service's configured one,
   and on spikes of signature-validation failures from single clients.
7. Test defensively in staging: send `none`-algorithm and
   algorithm-swapped tokens and confirm rejection; include this in
   regression tests.
8. Rotate keys if exploitation is suspected: a successful forgery
   means the signing key may be compromised — rotate and investigate.

## Expected outputs

- Algorithm pinning enforced in every validating service, with code
  or config evidence.
- Detection alerts for `none` and mismatched-algorithm tokens.
- Regression tests covering algorithm-confusion cases.
- A key-rotation plan ready for suspected compromise.

## Pitfalls

- "We only issue RS256, so we're fine": issuance and validation are
   separate — validation is where the flaw lives.
- Library upgrades resetting configuration to permissive defaults.
- Accepting tokens from multiple issuers with different algorithms
   without per-issuer pinning.
- Logging full tokens in detection rules: log the header claims, not
   the signature or sensitive claims.

## References

- OWASP JWT Cheat Sheet for Java (applicable principles across languages)
- RFC 7519 (JSON Web Token) and RFC 7518 (JWA)
- Auth0 documentation on JWT validation best practices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
