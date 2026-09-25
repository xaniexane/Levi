---
skill_id: cyber_detecting_api_enumeration_attacks
name: Detecting API Enumeration Attacks
description: Detect attackers mapping your API surface with rate, pattern, and error-code analysis on API gateway logs.
risk: info
permissions: []
requires_confirmation: false
tags: [api, detection, web]
version: 1.0.0
---
## Purpose

Catch adversaries systematically mapping your APIs — fuzzing endpoints, iterating IDs, and harvesting error messages — before enumeration turns into exploitation. Enumeration is the reconnaissance phase of API attacks; detecting it buys time to harden.

## When to use

- Protecting public or partner-facing APIs (REST, GraphQL) from reconnaissance.
- Investigating a spike in 404/400 responses or unusual API traffic patterns.
- Validating that API rate limiting and WAF rules are actually working.
- Post-incident analysis of how an attacker mapped the API before exploiting it.

## Prerequisites

- Centralized API logs: gateway logs (Apigee, Kong, AWS API Gateway, Azure APIM) with client IP, API key/identity, endpoint, status code, and timestamp.
- Baseline of normal API usage: which clients call which endpoints at what rates.
- Rate-limiting and WAF already in place (detection complements, not replaces, prevention).
- Alerting path with the API owner identified for rapid response.

## Procedure

1. **Baseline normal API behavior per client.** For each API key/service identity, record: endpoints used, request rates, error-rate norms, and ID parameter patterns (sequential vs. random UUIDs). Enumeration stands out only against a known normal — build the baseline before writing detections.
2. **Detect endpoint and method fuzzing.** Alert on: high 404 rates from a single client (probing for hidden endpoints), unusual HTTP methods (TRACE, unexpected PUT/DELETE), and requests to undocumented or deprecated paths. A client hitting hundreds of non-existent endpoints is mapping, not using.
3. **Detect IDOR-style ID enumeration.** Alert on sequential or high-volume ID parameter iteration (`/users/1001`, `/users/1002`...), especially when the IDs don't belong to the caller's tenant. Correlate with 200-vs-403 ratios: many 200s on others' IDs means your authorization is broken, not just probed.
4. **Detect GraphQL introspection and field fuzzing.** Alert on introspection queries from non-development clients, deeply nested queries (DoS probing), and field-enumeration patterns. Disable introspection in production — then alert on anyone attempting it, since only attackers try.
5. **Analyze error-message harvesting.** Attackers learn from your errors. Alert on clients generating diverse error types rapidly (schema probing), and review what your errors leak: stack traces, internal paths, and database errors are intelligence for the attacker. Fix the leakage; detect the harvesting.
6. **Correlate with infrastructure signals.** Join enumeration patterns with: source IP reputation, newly registered API keys exhibiting the behavior immediately, and concurrent scanning of your web properties. Enumeration from bulletproof-hosting ASNs on a day-old key is hostile until proven otherwise.
7. **Respond with graduated controls.** First: tighten rate limits for the offending client/key automatically. Then: challenge (CAPTCHA/proof-of-work) or suspend the key, block the source at the WAF, and notify the API owner. For confirmed malicious enumeration, preserve logs and rotate any credentials the enumeration may have exposed.

## Expected outputs

- Per-client API baselines with detections for endpoint fuzzing, ID enumeration, and introspection abuse.
- Error-message hygiene review (no stack traces or internal details leaked).
- Graduated response: auto rate-limit → challenge/suspend → block, with API-owner notification.

## Pitfalls

- No per-client baselines — global thresholds miss low-and-slow enumeration from a single key.
- Alerting on 404s without context — legitimate clients hit dead endpoints; the pattern matters, not the count.
- Leaving GraphQL introspection enabled in production — you're handing attackers the schema.
- Verbose errors in production — every stack trace is a free reconnaissance report.
- Detecting enumeration but not checking authorization — the IDOR the enumeration finds is the real finding.

## References

- OWASP API Security Top 10 — API3 (Broken Object Property Level Authorization), API4 (Unrestricted Resource Consumption)
- MITRE ATT&CK T1595 (Active Scanning) applied to API surfaces
- API gateway documentation (rate limiting, logging) for your platform
- NIST SP 800-95 (Guide to Secure Web Services)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
