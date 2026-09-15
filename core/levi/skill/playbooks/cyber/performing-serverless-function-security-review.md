---
skill_id: cyber_performing_serverless_function_security_review
name: Serverless Function Security Review
description: Review serverless functions and their cloud configurations for over-privileged roles, injection flaws, and event-source risks.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, serverless, appsec]
version: 1.0.0
---

## Purpose
- Find the IAM, injection, and event-handling weaknesses common in serverless applications.
- Ensure functions run with least-privilege roles instead of the broad defaults developers tend to accept.
- Validate that event sources cannot be abused to trigger functions with attacker-controlled input.

## When to use
- During cloud application security reviews and pre-production assessments.
- When serverless footprints grow faster than the security team's visibility.
- After incidents involving abused cloud functions or leaked function credentials.
- When building secure serverless baselines and guardrails.

## Prerequisites
- Inventory of functions, their triggers, and their IAM roles across accounts and regions.
- Read access to function code, infrastructure-as-code templates, and IAM policies.
- Cloud logging enabled: function invocation logs and CloudTrail or equivalent.
- A test environment where functions can be invoked safely.

## Procedure
1. Inventory every function with its runtime, triggers, environment variables, and attached IAM role.
2. Review IAM roles for least privilege: flag wildcard actions, wildcard resources, and unused permissions.
3. Check environment variables and secret handling: no hardcoded credentials, secrets in a managed vault with rotation.
4. Analyze event inputs for injection: S3 object keys, API Gateway payloads, queue messages, and scheduled event data.
5. Review function code for classic flaws: injection, insecure deserialization, SSRF via fetched URLs, and verbose error messages.
6. Assess trigger authorization: who can invoke the function, and are API endpoints authenticated and rate-limited.
7. Check deployment security: code signing or provenance verification, and separation of deployment roles from runtime roles.
8. Review logging and monitoring: structured logs without sensitive data, alerts on error spikes and unusual invocations.
9. Evaluate dependency hygiene: pinned versions, vulnerability scanning, and minimal deployment packages.
10. Check data protection: encryption in transit and at rest for function payloads and connected storage.
11. Test in the non-production environment with malformed and malicious event payloads.
12. Deliver findings with IaC-ready remediation so fixes land in templates, not just consoles.

## Expected outputs
- A per-function findings register with IAM, code, and configuration issues.
- IaC remediation snippets for the affected templates.
- Least-privilege role definitions for common function patterns.
- A serverless secure-baseline template for new functions.
- Guardrail policies blocking the riskiest configurations at deploy time.

## Pitfalls
- Reviewing code while ignoring the IAM role, which is where serverless breaches usually start.
- Trusting event input because it comes from another AWS or cloud service; attackers can often influence it.
- Leaving functions with old runtimes that no longer receive security patches.
- Reviewing one region while functions run in others; enumerate globally.

## References
- CIS cloud benchmarks for the provider in use
- OWASP Serverless Top 10
- AWS Lambda security best practices documentation
- NIST SP 800-53 controls on least privilege and cloud security
- Cloud provider documentation on function IAM roles and VPC configuration
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
