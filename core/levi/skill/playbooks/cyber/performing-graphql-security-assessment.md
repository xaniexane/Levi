---
skill_id: cyber_performing_graphql_security_assessment
name: GraphQL Security Assessment
description: Assess a GraphQL API for authorization, injection, and abuse flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [api, graphql, assessment]
version: 1.0.0
---
# GraphQL Security Assessment

## Purpose

GraphQL APIs concentrate an application's data model behind a single
endpoint, which makes authorization and abuse flaws high-impact. This
playbook provides a defensive assessment methodology: mapping the schema,
testing authorization per field, and checking abuse controls — with
written authorization, against systems you may test.

## When to use

- Security review of a GraphQL API before launch or a major release.
- Re-assessing after an API abuse incident.
- Validating fixes for previously reported GraphQL findings.
- Building an API security baseline for the organization.

## Prerequisites

- Written authorization defining the target API, test accounts of
  different privilege levels, and the testing window.
- A test environment mirroring production, or explicit permission to
  test production with safe, non-destructive cases.
- Tooling: an intercepting proxy (Burp Suite), GraphQL-aware extensions
  (InQL, GraphQL Raider), and multiple test identities.

## Procedure

1. Map the attack surface: obtain the schema through authorized means
   (provided schema, dev introspection) and inventory all queries,
   mutations, subscriptions, and their arguments.
2. Test authorization field by field: for every sensitive field and
   mutation, replay it as a low-privilege user, as another tenant's
   user, and unauthenticated — GraphQL's per-field resolution makes
   object-level authorization failures common.
3. Check for IDOR via global IDs: mutate object references (base64 IDs,
   sequential integers) across tenants and confirm the server enforces
   ownership, not just ID validity.
4. Test injection: pass GraphQL arguments into SQL, NoSQL, OS command,
   and template contexts; frameworks do not sanitize for you.
5. Evaluate abuse controls: verify depth limits, complexity analysis,
   pagination caps, and rate limiting are present and effective by
   sending attack-shaped queries and confirming cheap rejection.
6. Review introspection and tooling exposure: confirm introspection is
   off in production and no GraphiQL/Playground endpoints are reachable
   externally.
7. Inspect error handling: trigger errors and check that stack traces,
   internal field names, and backend details do not leak to clients.
8. Document findings with reproducible requests: each issue needs the
   exact query, the two identities compared (authorized vs. not), and
   the expected versus actual behavior.

## Expected outputs

- A schema inventory with per-field authorization test results.
- Findings with reproducible queries and impact ratings.
- Abuse-control verification results (depth, complexity, rate limits).
- A retest plan for validating remediation.

## Pitfalls

- Testing only as an admin: most GraphQL auth flaws appear at low
   privilege.
- Trusting framework defaults: resolvers enforce nothing unless the
   developer wrote the check.
- Skipping subscriptions: real-time endpoints get the same
   authorization scrutiny as queries.
- Destructive testing in production: mutations can alter real data —
   prefer staging.

## References

- OWASP API Security Top 10
- OWASP GraphQL Cheat Sheet
- MITRE ATT&CK: Valid Accounts (T1078) for authorization-testing context
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
