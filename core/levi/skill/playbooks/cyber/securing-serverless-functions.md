---
skill_id: cyber_securing_serverless_functions
name: Securing Serverless Functions
description: Harden serverless functions across providers: input validation, least-privilege roles, and abuse-resistant design.
risk: info
permissions: []
requires_confirmation: false
tags: [serverless, cloud, hardening]
version: 1.0.0
---
## Purpose
Serverless functions inherit the provider's infrastructure security but expose application-layer risk: event injection, over-privileged roles, secret leakage, and cost-amplifying abuse. This provider-neutral playbook hardens functions and their triggers regardless of cloud.

## When to use
- Serverless security standards for development teams.
- Pre-production review of event-driven architectures.
- After incidents involving function abuse or leaked credentials.
- Cost or abuse anomalies traced to serverless endpoints.

## Prerequisites
- Inventory of functions, triggers (HTTP, queue, storage, schedule), and roles.
- Centralized logging for function invocations and errors.
- Secrets manager integrated with the deployment pipeline.
- Threat model of event sources: which are trusted vs attacker-influenced.

## Procedure
1. Validate and sanitize every event input; treat HTTP bodies, queue messages, and storage object names as untrusted.
2. Assign least-privilege execution roles per function; scope to specific resources and actions.
3. Keep secrets in the provider's secrets manager; never in environment variables or code.
4. Authenticate and authorize HTTP triggers; do not rely on unguessable URLs as the only control.
5. Set concurrency/throughput limits and timeouts to bound cost and blast radius from abuse or bugs.
6. Pin dependency versions, scan them, and minimize the deployment package to reduce attack surface.
7. Log invocations with correlation IDs; alert on error spikes, duration anomalies, and permission denials.
8. Design idempotent handlers so retried or replayed events cannot cause duplicate side effects.
9. Map event-source permissions; overly broad invoke rights let one compromised function trigger others.
10. Encrypt and monitor dead-letter queues; they accumulate sensitive failed payloads.
11. Review provisioned-concurrency settings; idle warm functions still count as attack surface.

## Expected outputs
- Per-function security checklist results.
- Least-privilege role definitions with usage justification.
- Monitoring and cost-anomaly alerting for serverless estates.
- Event-source permission map with least-privilege findings.
- Dead-letter queue encryption and monitoring status.
- Provisioned-concurrency review results.

## Pitfalls
- Public HTTP triggers without auth are the top serverless exposure; audit them first.
- Event-source mapping misconfigurations can silently drop or duplicate events.
- Cold starts tempt developers to over-provision permissions 'just in case'; resist it.
- Provider defaults vary; verify encryption, logging, and network settings rather than assuming.
- Dead-letter queues accumulate sensitive payloads; encrypt and monitor them.
- Event filtering misconfigurations cause silent data loss; test filters explicitly.
- Vendor-specific defaults differ; verify each provider's settings rather than assuming parity.
- Cold-start behavior differences can leak timing information; avoid branching on secrets.

## References
- NIST SP 800-204, Security Strategies for Microservices-based Applications.
- OWASP Serverless Top 10.
- Cloud provider serverless security documentation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
