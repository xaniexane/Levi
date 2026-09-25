---
skill_id: cyber_detecting_shadow_api_endpoints
name: Detecting Shadow API Endpoints
description: Discover undocumented and unmanaged API endpoints in your environment.
risk: low
permissions: []
requires_confirmation: false
tags: [api-security, asset-discovery, detection]
version: 1.0.0
---
## Purpose

Shadow APIs — endpoints deployed without security review, documentation, or ownership — are invisible to testing and monitoring, making them ideal targets. This playbook covers discovering shadow APIs through traffic analysis, gateway comparison, and code/repository scanning, then bringing them under management.

## When to use

- An API security assessment found endpoints nobody owns.
- You need to inventory APIs across cloud, on-prem, and SaaS integrations.
- A breach involved an undocumented endpoint.
- Building an API security program from zero.

## Prerequisites

- API gateway / WAF / load-balancer logs showing requested paths and hosts.
- Code and IaC repository access for route discovery (source-of-truth comparison).
- DNS and certificate-transparency data for discovering API-ish subdomains.
- An approved API catalog (even partial) to diff against.

## Procedure

1. Discover APIs from traffic, not documentation. Aggregate gateway/WAF/proxy logs for distinct (host, path-prefix) combinations over 30+ days. Paths receiving traffic that aren't in the approved catalog are candidate shadow APIs. Include east-west traffic — internal-only shadow APIs are common and still reachable by compromised hosts.
2. Discover from code and infrastructure. Scan repositories and IaC for route definitions, OpenAPI specs, and serverless function triggers; compare against the traffic-derived list. Code-deployed endpoints with no traffic may be dormant-but-exploitable; traffic-observed endpoints with no code are misconfigurations or compromises — investigate both directions of the mismatch.
3. Discover from the edge. Use certificate-transparency logs and DNS enumeration for api-/internal-/dev- style subdomains, and scan cloud accounts for API Gateway / App Service / Cloud Run resources outside central management. Shadow APIs love forgotten dev/staging environments that were never decommissioned.
4. Triage each shadow endpoint. For each: identify the owner (code history, deployer identity), determine data sensitivity (auth requirements, PII exposure), assess security posture (authentication, rate limiting, input validation, logging), and check access logs for prior abuse. Prioritize internet-facing + sensitive-data + no-authentication combinations.
5. Bring shadows into the light or shut them down. For legitimate endpoints: register in the API catalog, assign an owner, add to gateway management with authentication/rate-limiting/logging, and include in security testing. For unjustified endpoints: decommission after a deprecation notice. Track every discovered endpoint to a managed-or-removed state.
6. Prevent recurrence: require gateway registration for new APIs (policy + pipeline checks), run discovery on a schedule, and include API inventory in change management. Shadow APIs regrow wherever deployment is easier than registration — fix the friction, not just the findings.

## Expected outputs

- Traffic-derived API inventory diffed against the approved catalog.
- Code/IaC-derived endpoint list with mismatch analysis.
- Per-endpoint triage: owner, data sensitivity, security posture, abuse check.
- Governance: registration requirement, scheduled re-discovery, decommission log.

## Pitfalls

- Path-only inventory misses versioned and parameterized endpoints — normalize paths before diffing.
- Internal-only shadow APIs are still attacker-reachable post-compromise — don't deprioritize them entirely.
- Decommissioning without traffic analysis breaks unknown consumers — monitor before removing.
- API gateways only see what routes through them — direct-to-origin and sidecar APIs need code/network discovery.
- One-time discovery decays immediately — schedule it like vulnerability scanning.

## References

- OWASP API Security Top 10 (API9:2023 Improper Inventory Management); NIST SP 800-204 (microservices/API security); MITRE ATT&CK T1595.002 (Active Scanning) adapted for API discovery
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
