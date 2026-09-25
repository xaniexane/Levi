---
skill_id: cyber_performing_http_parameter_pollution_attack
name: HTTP Parameter Pollution Defense
description: Detect and prevent HTTP parameter pollution in web applications.
risk: low
permissions: []
requires_confirmation: false
tags: [web, hardening, detection]
version: 1.0.0
---
# HTTP Parameter Pollution Defense

## Purpose

HTTP Parameter Pollution (HPP) sends multiple values for the same
parameter (`?id=1&id=2`) to exploit differences in how servers, proxies,
and frameworks parse them — bypassing filters or altering logic. This
defensive playbook covers detecting HPP attempts and hardening
applications so duplicate parameters are handled safely.

## When to use

- Hardening web applications and APIs against input-manipulation
  attacks.
- Investigating WAF alerts for duplicated query parameters.
- Reviewing filter bypasses where validation passed but behavior was
  wrong.
- Validating proxy/backend parsing consistency in the request chain.

## Prerequisites

- Access to application source or framework documentation for
  parameter parsing behavior, plus WAF or application logs with raw
  query strings.
- A test environment where you may send crafted requests.
- Knowledge of the full request chain: CDN, WAF, reverse proxy,
  application server — each may parse differently.

## Procedure

1. Determine your stack's parsing behavior: for each framework in the
   chain, document whether duplicate parameters yield first value,
   last value, an array, or concatenation — mismatches are the
   vulnerability.
2. Detect HPP in logs: search WAF and application logs for repeated
   parameter names in a single request, especially on parameters used
   for access control, pricing, or filtering.
3. Harden at the application layer: explicitly reject requests with
   duplicate security-relevant parameters, or define and document
   which occurrence wins — never leave it to framework default.
4. Normalize at the edge: configure the WAF or proxy to block or
   normalize duplicated parameters before they reach the application.
5. Test filter bypasses defensively: replay blocked payloads with
   duplicated parameter names against staging to confirm the WAF and
   application agree on the outcome.
6. Review client-side parameter construction: ensure the application
   itself never generates duplicate parameters that backends resolve
   inconsistently.
7. Add detection rules: alert on repeated high-value parameter names
   (`role`, `price`, `user_id`, `redirect`) from single clients.
8. Verify after changes: repeat the crafted-request tests in staging
   and confirm uniform, documented behavior across the chain.

## Expected outputs

- A parsing-behavior matrix for the request chain with mismatches
  documented.
- Application and WAF handling for duplicate parameters defined and
  tested.
- Detection rules for HPP probing with alert destinations.
- Verification evidence from staging tests.

## Pitfalls

- Fixing only the application while the WAF parses differently: the
   chain is only as consistent as its most divergent member.
- Rejecting duplicates globally without checking legitimate clients
   that repeat parameters (some do) — measure before blocking.
- Treating HPP as purely a WAF problem: business logic must define
   correct behavior.
- Logging without raw query strings: you cannot detect what you do
   not record.

## References

- OWASP Testing Guide: Testing for HTTP Parameter Pollution
- OWASP Web Security Testing Guide (input validation sections)
- Framework documentation on query-string parsing behavior
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
