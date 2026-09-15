---
skill_id: cyber_performing_graphql_depth_limit_attack
name: GraphQL Depth-Limit Attack Defense
description: Detect and mitigate GraphQL query-depth and complexity denial-of-service.
risk: low
permissions: []
requires_confirmation: false
tags: [api, graphql, hardening]
version: 1.0.0
---
# GraphQL Depth-Limit Attack Defense

## Purpose

GraphQL lets clients shape their own queries — including deeply nested
ones that can exhaust a server. Attackers abuse this for denial of
service via query depth and complexity. This defensive playbook covers
detection of abusive queries and the hardening controls that neutralize
them.

## When to use

- Hardening a GraphQL API before production or after a DoS incident.
- Detecting resource-exhaustion attacks against GraphQL endpoints in
  WAF or application logs.
- Reviewing whether existing depth/complexity limits are effective.
- Validating API gateway policies for GraphQL traffic.

## Prerequisites

- Access to GraphQL server configuration and application/WAF logs
  showing full query text or at least operation signatures.
- Knowledge of the framework in use (Apollo, graphql-java, Strawberry,
  etc.) since limit mechanisms differ.
- A baseline of legitimate query shapes from production traffic.

## Procedure

1. Verify depth limiting is enabled: set a maximum query depth (a
   starting point of 7–10, tuned to the schema) and reject deeper
   queries with a clear error — depth alone is necessary but not
   sufficient.
2. Add query-complexity analysis: assign costs to fields (expensive
   resolvers cost more) and enforce a maximum total complexity per
   request, since a shallow query can still fan out massively.
3. Cap pagination: enforce maximum `first`/`last` page sizes and require
   bounded connections so list fields cannot be abused for bulk data
   extraction.
4. Implement persisted queries or an allowlist for high-risk clients:
   pre-register legitimate operations and reject arbitrary query text.
5. Add rate limiting keyed on authenticated identity and query
   complexity, not just request count — a complexity-weighted budget
   stops expensive queries from a single account.
6. Detect attacks in logs: look for repeated 400s on depth/complexity
   errors from one client, queries with extreme nesting, and latency
   spikes correlated with specific operations.
7. Alert on abuse patterns: WAF rules flagging deeply nested braces or
   repeated field aliases, plus application alerts on resolver timeouts
   and memory pressure during query execution.
8. Load-test the limits: replay captured abusive queries against the
   hardened endpoint in staging to confirm rejection is cheap and fast.

## Expected outputs

- Enforced depth and complexity limits with documented values and
  rationale.
- Complexity-weighted rate limiting and pagination caps.
- Detection rules for depth/complexity abuse with alert destinations.
- Load-test evidence that limits hold under attack-shaped traffic.

## Pitfalls

- Relying on depth limits alone: alias-heavy or wide shallow queries
  bypass them.
- Setting limits from guesswork: derive them from real production
   query shapes or you will break legitimate clients.
- Rate-limiting by IP only: NAT and shared egress make this unreliable
   — key on identity plus complexity.
- Returning verbose errors that leak schema details to attackers.

## References

- OWASP API Security Top 10 (API4:2023 Unrestricted Resource Consumption)
- Apollo GraphQL documentation on query depth limiting and complexity
- graphql-java documentation: MaxQueryDepthInstrumentation and complexity analysis
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
