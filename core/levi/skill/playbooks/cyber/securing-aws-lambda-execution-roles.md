---
skill_id: cyber_securing_aws_lambda_execution_roles
name: Securing AWS Lambda Execution Roles
description: Harden Lambda execution roles and function configuration: least privilege, VPC design, and secret handling.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, aws, lambda]
version: 1.0.0
---
## Purpose
Lambda functions often run with far more permission than they need, and their event-driven nature widens the blast radius of a compromise. This playbook hardens both the execution role and the function configuration: least-privilege policies, sensible networking, encrypted environment, and safe secret handling.

## When to use
- Serverless security review or new Lambda development standards.
- After an incident involving a compromised function or leaked role credentials.
- Pre-production checklist for Lambda-based services.
- Remediating CSPM findings on over-privileged execution roles.

## Prerequisites
- Inventory of Lambda functions with their execution roles and triggers.
- CloudTrail and X-Ray/logging for understanding actual function behavior.
- Secrets Manager or Parameter Store for secret centralization.
- Deployment pipeline where role changes can be tested.

## Procedure
1. Inventory each function's triggers, environment variables, and the execution role's policies.
2. Right-size the role: allow only the specific actions and resources the function uses (verify with CloudTrail).
3. Give each function its own role; never share one broad role across functions.
4. Store secrets in Secrets Manager/Parameter Store; never in plaintext environment variables.
5. Encrypt environment variables with a customer-managed KMS key where sensitive data is present.
6. Attach to a VPC only when the function needs private resources; otherwise keep it outside for a smaller footprint.
7. Set reserved concurrency to bound blast radius and cost from abuse or loops.
8. Add structured logging and alerts for permission errors, unusual invocations, and duration spikes.
9. Review Lambda layers and extensions; they run with the function's privileges and are often forgotten.
10. Audit Lambda function URLs; they create public endpoints that need API-grade protection.
11. Check event source mappings for overly broad permissions that let one function trigger others.

## Expected outputs
- Per-function least-privilege role policies with usage evidence.
- Function configuration checklist results (secrets, VPC, concurrency, encryption).
- Monitoring rules for anomalous Lambda activity.
- Layer and extension inventory with privilege review.
- Function URL audit with auth status per URL.
- Event-source permission review results.

## Pitfalls
- Wildcard resource grants on DynamoDB/S3 are common; scope to specific tables and prefixes.
- VPC-attached functions need NAT and add cold-start latency; only use when required.
- Environment variables are visible to anyone with lambda:GetFunctionConfiguration; treat them as non-secret.
- Recursive invocation (function triggering itself) causes runaway cost; set concurrency and add circuit breakers.
- Function URLs are public by default with the wrong auth type; audit them like internet APIs.
- Layers from third parties are supply-chain risk; pin and verify them.
- Dead-letter queues can accumulate sensitive payloads; encrypt and monitor them.
- Old function versions retain old permissions; clean up unused versions and their role bindings.

## References
- AWS Documentation: Lambda security and execution roles.
- AWS Well-Architected Framework: Security Pillar (serverless).
- CIS Amazon Web Services Foundations Benchmark.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
