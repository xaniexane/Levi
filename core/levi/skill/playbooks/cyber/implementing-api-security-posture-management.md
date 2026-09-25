---
skill_id: cyber_implementing_api_security_posture_management
name: API Security Posture Management
description: Establish continuous discovery, risk assessment, and governance for every API in the estate.
risk: low
permissions: []
requires_confirmation: false
tags: [api, posture-management]
version: 1.0.0
---
## Purpose
APIs are the largest unaudited attack surface in most organizations: shadow APIs, stale versions,
and endpoints that expose more data than their consumers need. This playbook establishes an API
security posture management (ASPM) program — continuous discovery, inventory, risk scoring, and
remediation governance — so every API is known, owned, classified, and held to a security baseline.

## When to use
- Standing up an API security program or maturing an ad-hoc one into a governed process.
- After an audit or incident finding: "we did not know that API existed" (shadow/orphaned APIs).
- Before/after a platform migration, M&A integration, or major partner-onboarding wave that
  multiplies API sprawl.
- When compliance (PCI DSS, SOC 2, GDPR) requires an inventory of data-exposing interfaces.
- As the governance layer beneath API testing, WAF rules, and gateway policy (companion playbooks:
  API security testing, API threat protection).

## Prerequisites
- Executive sponsorship: API owners must accept remediation deadlines; posture management without
  enforcement is a dashboard, not a control.
- An authoritative starting inventory: API gateway exports, cloud asset inventories, service meshes,
  and developer surveys to seed discovery.
- A data-classification scheme (public / internal / confidential / regulated) so posture findings
  can be risk-weighted.
- A posture tool or platform (gateway-native analytics, dedicated ASPM product, or CMDB-backed
  process) plus a ticketing system for remediation tracking.
- Defined API security baseline: authentication required, TLS 1.2+, schema validation, rate
  limiting, logging — documented before scoring starts.

## Procedure
1. **Discover continuously, not once.** Connect discovery sources: API gateways (publish events),
   cloud provider APIs, service mesh telemetry, DNS/passive discovery, and code scanning for route
   definitions. Deduplicate by host + path + method. Treat discovery as a feed, not a project.
2. **Build the authoritative inventory.** For each API record: owner team, environment,
   gateway/ingress, authentication type, data classification of payloads, version, and lifecycle
   state (dev/stage/prod/deprecated). Unknown owner is itself a finding — assign via service catalog
   or escalate.
3. **Classify by data and exposure.** Tag APIs that handle regulated data (PII, payment, health) and
   those exposed to the internet vs. internal-only. A public API returning internal-tier data is
   your highest-priority mismatch.
4. **Score posture against the baseline.** Evaluate each API for: authentication strength,
   authorization granularity (BOLA risk), TLS configuration, schema/contract validation, rate
   limiting, CORS policy, error verbosity (stack traces, internal IDs), deprecated version still
   serving, and logging coverage. Weight failures by data classification and exposure.
5. **Hunt shadow and zombie APIs.** Flag endpoints seen in traffic but absent from the inventory
   (shadow), and documented/deprecated versions still receiving production traffic (zombies).
   Require owners to register or decommission; zombies get a sunset date with enforcement.
6. **Prioritize with exploitability, not just misconfiguration count.** Rank findings by: internet
   exposure x sensitive data x missing auth x active traffic. A low-traffic internal API missing
   rate limiting is a backlog item; a public payments endpoint without auth is a drop-everything
   incident.
7. **Drive remediation through owners.** Open tickets with evidence (request samples, config
   excerpts), a specific fix, and a deadline tied to severity. Track mean-time-to-remediate per
   team; publish posture trends to engineering leadership monthly.
8. **Validate fixes, don't trust tickets.** Re-test closed findings within the same posture pipeline
   before marking resolved. Regression-check monthly — gateways get reconfigured, new versions ship,
   posture decays.
9. **Feed the rest of the program.** Export the ranked inventory to: the API testing backlog (test
   highest-risk first), WAF/gateway policy (protect what you can't fix fast), and the threat model
   (data flows for new features).
10. **Report posture as a trend, not a snapshot.** Track: percent of APIs inventoried with owners,
    percent meeting baseline, mean age of open critical findings, and shadow-API discovery rate.
    Present deltas, not totals, to leadership.

## Expected outputs
- A continuously updated API inventory with owners, exposure, data classification, and lifecycle
  state.
- A scored posture report: findings ranked by risk, assigned to owners, with remediation deadlines.
- Shadow and zombie API lists with registration or decommission decisions.
- Monthly posture trend metrics and MTTR per team.
- A tested API security baseline document referenced by engineering standards.

## Pitfalls
- Discovery that only covers the gateway: APIs served directly from cloud functions, legacy VMs, or
  partner connections bypass it. Layer traffic-based and code-based discovery.
- Scoring everything equally: without data-classification weighting, teams drown in low-value
  findings and ignore the critical ones.
- Accepting "we'll fix it in the rewrite": zombie APIs serving production traffic are live attack
  surface; enforce sunset dates.
- Treating the posture tool's defaults as your policy: tune severity to your threat model, or every
  dashboard goes red and nobody acts.
- Skipping validation of fixes: a closed ticket without re-testing is a hope, not a control.

## References
- OWASP API Security Top 10 (risk categories for API posture scoring)
- NIST SP 800-204 (security for microservices-based applications, API gateway guidance)
- PCI DSS v4.0 Requirement 1 and 6 (inventory and secure configuration of in-scope APIs)
- MITRE ATT&CK T1190 (Exploit Public-Facing Application) and T1557 (Adversary-in-the-Middle)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
