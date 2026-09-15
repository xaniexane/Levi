---
skill_id: cyber_performing_graphql_introspection_attack
name: GraphQL Introspection Attack Defense
description: Detect introspection abuse and lock down GraphQL schema exposure.
risk: low
permissions: []
requires_confirmation: false
tags: [api, graphql, hardening]
version: 1.0.0
---
# GraphQL Introspection Attack Defense

## Purpose

GraphQL introspection lets any client download the full schema — every
type, field, and mutation — which attackers use to map the API for
follow-on abuse. This defensive playbook covers detecting introspection
probing and hardening the endpoint so the schema is not handed to
adversaries.

## When to use

- Hardening a production GraphQL API.
- Investigating whether an attacker mapped your API before an abuse
  incident.
- Reviewing schema exposure as part of an API security assessment.
- Validating gateway or WAF rules for GraphQL traffic.

## Prerequisites

- Access to GraphQL server configuration and logs with query text or
  operation names.
- An inventory of which clients legitimately need introspection
  (usually only development tooling like GraphiQL).
- Baseline knowledge of normal query patterns for the API.

## Procedure

1. Disable introspection in production: set `introspection: false`
   (Apollo) or the equivalent in your framework; keep it enabled only
   in development environments behind authentication.
2. Remove development tooling from production: GraphiQL, Playground,
   and Voyager endpoints should not be deployed or reachable outside
   dev.
3. Detect probing in logs: queries containing `__schema` or `__type`
   from external clients are reconnaissance — alert on them,
   especially repeated or paginated introspection.
4. Watch for introspection alternatives: attackers also use field
   suggestion errors and brute-force field names — monitor for high
   rates of "field does not exist" errors from single clients.
5. Apply the principle of least schema: split public and internal
   schemas if the framework supports it, so even a leaked schema
   reveals only public operations.
6. Add WAF coverage: block or alert on `__schema`/`__type` patterns in
   request bodies at the edge, as defense in depth behind the server
   setting.
7. Audit for historical exposure: if introspection was ever enabled in
   production, assume the schema is known — review mutations and
   sensitive fields for authorization flaws rather than relying on
   obscurity.
8. Verify the fix: send an introspection query from an unauthenticated
   external client and confirm it is rejected; repeat after every
   deployment.

## Expected outputs

- Introspection disabled in production with config evidence.
- Detection alerts for `__schema`/`__type` probing.
- A schema-exposure assessment: what is public versus internal.
- Verification tests confirming rejection of introspection queries.

## Pitfalls

- Disabling introspection but leaving GraphiQL deployed: the UI is the
   leak.
- Believing disabling introspection fixes authorization bugs: it only
   slows reconnaissance.
- Forgetting staging environments: a staging API with introspection
   on often mirrors production's schema.
- Blocking `__schema` at the WAF while the server still answers it to
   direct hits.

## References

- OWASP API Security Top 10 (API3:2023 Broken Object Property Level Authorization)
- Apollo GraphQL documentation on disabling introspection in production
- GraphQL specification: introspection schema documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
