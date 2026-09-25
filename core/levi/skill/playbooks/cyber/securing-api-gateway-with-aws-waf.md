---
skill_id: cyber_securing_api_gateway_with_aws_waf
name: Securing API Gateways with AWS WAF
description: Protect API Gateway with AWS WAF: managed rules, rate limiting, logging, and continuous tuning.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, aws, waf]
version: 1.0.0
---
## Purpose
AWS WAF in front of API Gateway blocks common web attacks, bots, and abuse before they reach your APIs. This playbook covers deploying it as a defensive control: rule selection, rate limiting, logging to SIEM, and the tuning cycle that keeps false positives low while attacks are blocked.

## When to use
- Exposing APIs to the internet via API Gateway.
- After observing scraping, credential stuffing, or injection attempts against APIs.
- Compliance requirements for web application firewall coverage.
- Pre-launch hardening of a new public API.

## Prerequisites
- API Gateway (REST or HTTP) deployed with defined stages and routes.
- Understanding of API traffic patterns: clients, rates, and expected payloads.
- Log destination (S3/CloudWatch/Firehose) and SIEM ingestion path.
- Change process for WAF rule updates.

## Procedure
1. Associate a WAF web ACL with the API Gateway stage; start in count (monitor) mode.
2. Enable AWS managed rule groups: core rule set, known bad inputs, and IP reputation lists.
3. Add rate-based rules per route: strict limits on auth endpoints, generous on read endpoints.
4. Write custom rules for API-specific abuse: oversized bodies, unexpected content types, known attack strings.
5. Enable full WAF logging; ship to SIEM and build dashboards for blocked vs counted requests.
6. Tune: review false positives weekly, add scoped exclusions rather than disabling rules.
7. Test rule changes against recorded attack traffic before enforcing.
8. Review quarterly: new managed rules, changed API routes, and evolving abuse patterns.
9. Create a canary rule group to test new rules against mirrored production traffic.
10. Review WAF body-inspection size limits; large uploads bypass inspection silently.
11. Tune bot-control rules against your legitimate automation (monitoring, partners) to avoid breakage.

## Expected outputs
- WAF web ACL configuration with rule inventory and rationale.
- Rate-limit policy per route with business justification.
- Logging pipeline and tuning runbook.
- Canary testing procedure for rule changes.
- Body-inspection limit documentation and compensating controls.
- Bot-control allowlist for legitimate automation.

## Pitfalls
- Enforcing untested managed rules breaks legitimate clients; always start in count mode.
- One global rate limit either blocks real users or misses targeted abuse; scope per route.
- WAF does not fix broken access control or business logic; it is one layer.
- Rule costs scale with requests; monitor the bill alongside the security value.
- WAF request-body inspection has size limits; oversized bodies skip inspection.
- Bot management rules can block legitimate partner integrations; allowlist carefully.
- Regional WAF and CloudFront WAF have different feature sets; design for the right one.
- WAF logs without a review cadence are write-only; assign weekly tuning ownership.

## References
- AWS Documentation: AWS WAF.
- AWS Documentation: API Gateway security.
- OWASP Core Rule Set documentation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
