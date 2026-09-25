---
skill_id: cyber_implementing_api_schema_validation_security
name: Implementing API Schema Validation Security
description: Enforce API schema validation as a security control: strict schemas, positive validation, and safe handling of schema evolution.
risk: low
permissions: []
requires_confirmation: false
tags: [api, application-security, sdlc]
version: 1.0.0
---
## Purpose

Schema validation is a security control, not just a correctness nicety:
strict positive validation at the API boundary blocks injection,
deserialization, and business-logic attacks that exploit unexpected input
shapes. This playbook covers implementing schema validation that actually
protects — strictness, completeness, and safe evolution.

## When to use

- Designing or reviewing API input handling.
- Remediating injection or mass-assignment findings.
- Standardizing validation across microservices.
- After incidents where malformed input caused security impact.

## Prerequisites

- API specifications (OpenAPI/JSON Schema) for in-scope services.
- Validation enforcement point: gateway and/or service frameworks.
- Inventory of endpoints accepting complex input (nested objects,
  arrays, file uploads).
- CI integration for schema-contract testing.

## Procedure

1. **Write strict schemas.** Define every field: type, format, length/
   range limits, patterns, required vs. optional, and enumerated values
   where applicable. Reject unknown fields (`additionalProperties:
   false` equivalent) — mass-assignment attacks exploit permissive
   unknown-field handling.
2. **Validate positively, not negatively.** Allow-list what is
   accepted; do not try to blocklist bad input. Negative validation
   (blocking `<script>`, for example) is bypassable — positive
   validation of expected shapes is not.
3. **Enforce at the trust boundary.** Validate at the gateway for
   coarse checks (size, content-type, structure) and in the service
   for semantic checks (business rules, authorization context).
   Never trust client-side validation — it is UX, not security.
4. **Constrain dangerous shapes.** Set maximum string lengths, array
   sizes, nesting depth, and request-body sizes to bound resource
   consumption (ReDoS via regex patterns, billion-laughs via nested
   objects, zip bombs via uploads). Test limits against real payloads.
5. **Handle polymorphism safely.** For polymorphic request bodies
   (oneOf/anyOf), validate the discriminator strictly and ensure each
   variant is fully constrained — attackers target the least-
   validated variant.
6. **Govern schema evolution.** Version schemas explicitly; additive
   changes only within a version; review every schema change for
   security impact (new optional fields become new attack surface).
   Deprecate permissive legacy schemas on a schedule.
7. **Test validation.** Include negative test cases in CI: oversized
   payloads, type confusion, unknown fields, deep nesting, and
   encoding tricks. Fuzz the validation layer itself periodically.
8. **Monitor validation failures.** Log and alert on validation-failure
   spikes per endpoint — they indicate either broken clients (fix the
   docs) or active probing (investigate the source).

## Expected outputs

- Strict schemas for all endpoints with unknown-field rejection.
- Enforcement at gateway and service layers with documented
  responsibilities.
- Resource-consumption limits tested against real payloads.
- CI negative-test suites and fuzzing coverage.
- Validation-failure monitoring with alerting.

## Pitfalls

- `additionalProperties: true` by default in many frameworks —
   explicitly lock it down.
- Client-side-only validation — trivially bypassed; always validate
   server-side.
- Regex patterns vulnerable to ReDoS — test patterns for
   catastrophic backtracking or avoid complex regexes.
- Schema drift: code accepts more than the published schema —
   generate validation from the same schema artifact as documentation.
- Overly strict validation breaking legitimate clients — measure
   failure rates before enforcing in blocking mode.

## References

- OWASP: API Security Top 10 (mass assignment, injection sections);
  Input Validation cheat sheet
- JSON Schema / OpenAPI specification documentation
- NIST SP 800-95: Guide to Secure Web Services
- CWE-20: Improper Input Validation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
