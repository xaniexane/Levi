---
skill_id: cyber_implementing_api_security_testing_with_42crunch
name: API Security Testing with 42Crunch
description: Integrate 42Crunch OpenAPI contract auditing and dynamic API testing into the delivery pipeline.
risk: low
permissions: []
requires_confirmation: false
tags: [api, testing]
version: 1.0.0
---
## Purpose
Most API vulnerabilities are design flaws in the contract — over-permissive schemas, missing auth
definitions, injection-friendly parameters — visible before a line of runtime code ships. This
playbook implements API security testing centered on 42Crunch: static auditing of OpenAPI/Swagger
contracts plus dynamic conformance and attack testing, wired into CI so insecure contracts fail the
build. (42Crunch is used here as the representative contract-security platform; the workflow applies
to any OpenAPI-native scanner.)

## When to use
- Shifting API testing left: catching contract flaws in pull requests instead of in penetration
  tests.
- Before exposing a new or v2 API to partners or the internet.
- After incidents rooted in BOLA/IDOR, mass assignment, or injection via API parameters.
- To satisfy secure-SDLC evidence requirements (SOC 2, PCI DSS 6.x) for API changes.
- Alongside the API posture management playbook: testing validates what posture scoring flags.

## Prerequisites
- OpenAPI (v3 preferred) specifications for the APIs under test, maintained as source of truth —
  testing a stale contract tests nothing.
- CI/CD access to add pipeline stages and fail builds on policy (coordinate with engineering leads
  on gating thresholds).
- A non-production environment with test data for dynamic scans, or a 42Crunch scan configuration
  pointed at staging.
- An API token/key for the scanner with least-privilege access to the target environment.
- A defined severity policy: which audit findings block merge vs. warn.

## Procedure
1. **Baseline your contracts.** Import every OpenAPI spec into 42Crunch (or the audit CLI) and run
   the static security audit. Record the baseline scores — you need the "before" number to prove the
   program works and to set realistic gates.
2. **Triage the audit findings by category.** Work through: authentication/authorization definitions
   (missing security schemes, overly broad scopes), data validation (loose schemas, missing max
   lengths, free-form objects enabling mass assignment), transport (HTTP schemes, weak TLS), and
   information leakage (verbose examples, internal URLs in descriptions). These are design fixes —
   cheapest to make now.
3. **Fix the contract, not just the code.** Require schema strictness: `additionalProperties: false`
   where appropriate, enums instead of free strings, explicit required fields, and string
   length/format constraints. A tight contract is the first and cheapest input-validation layer.
4. **Gate the pipeline on audit score.** Add a CI step that fails the build when the audit score
   drops below threshold or when new high-severity findings appear. Start in warn-only mode for two
   sprints, then enforce — engineers need time to clean legacy contracts.
5. **Generate dynamic tests from the contract.** Use the platform's scan capability to produce
   conformance tests (does the implementation match the contract?) and attack tests (fuzzed
   parameters, auth bypass attempts, injection payloads) against the staging environment.
6. **Run dynamic scans per-deployment for high-risk APIs.** For APIs handling sensitive data or
   internet-exposed, run the dynamic scan on every deployment to staging; for lower-risk APIs, run
   nightly or per-release. Scan reports attach to the release record.
7. **Triage dynamic findings with developers.** Distinguish contract violations (implementation
   drift — fix the code or update the contract deliberately) from genuine vulnerabilities (BOLA,
   injection — fix the code). File both in the backlog with severity and evidence.
8. **Protect the test environment.** Dynamic scans send attack traffic — run against staging with
   synthetic data, notify the environment owners, and exclude destructive tests (e.g., mass
   deletion) via scan profiles. Never point a fuzzer at production.
9. **Track metrics that drive behavior.** Per team: audit score trend, count of blocking findings
   introduced vs. fixed, dynamic-scan criticals per release, and time-to-fix. Review with
   engineering leadership monthly.
10. **Keep contracts as living documents.** Require contract updates in the same PR as API behavior
    changes, and re-audit on every change. A contract that drifts from reality silently disables
    every downstream control built on it.

## Expected outputs
- Audited OpenAPI contracts with recorded baseline scores and triaged findings.
- A CI gate that fails builds on new high-severity contract findings.
- Dynamic scan reports per release for high-risk APIs, with findings tracked to remediation.
- Team-level metrics: audit score trends, blocking findings, time-to-fix.
- A documented API security testing policy (thresholds, scan cadence, environment rules).

## Pitfalls
- Auditing specs nobody maintains: if the contract drifts from the implementation, both static and
  dynamic results are fiction. Enforce contract-as-code.
- Turning the gate on at full strictness day one: legacy contracts will fail hundreds of checks and
  engineers will bypass the gate. Phase in from warn to block.
- Running attack scans against production or shared staging without coordination — you will cause
  incidents and lose trust.
- Treating the audit score as security: a 90/100 contract can still hide business-logic flaws (BOLA,
  excessive data exposure) that only manual review and dynamic testing catch.
- Ignoring authentication testing: contract audits check that auth is *defined*, not that it is
  *enforced* — dynamic auth-bypass tests close that gap.

## References
- OWASP API Security Top 10 (what contract and dynamic testing must cover)
- 42Crunch API security platform documentation (audit rules, CI/CD integration, scan configuration)
- NIST SP 800-204A (API security controls for microservices)
- OWASP Testing Guide v4, API testing sections
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
