---
skill_id: cyber_detecting_serverless_function_injection
name: Detecting Serverless Function Injection
description: Detect code injection and abuse in serverless functions (Lambda, Cloud Functions).
risk: low
permissions: []
requires_confirmation: false
tags: [serverless, cloud, detection]
version: 1.0.0
---
## Purpose

Serverless functions execute attacker-influenced input by design — event payloads, query strings, queue messages — making injection (command, code, deserialization) a primary serverless threat. This playbook covers detecting injection in function telemetry: CloudWatch/CloudTrail signals, anomalous invocations, and the function-to-privilege-escalation paths unique to serverless.

## When to use

- You run production serverless workloads and need injection detection.
- A function processes untrusted input (webhooks, uploads, user data).
- CloudTrail shows anomalous Lambda invocations or role usage.
- Threat modeling identified serverless as an attack surface.

## Prerequisites

- Function logs (CloudWatch Logs / Cloud Logging) with invocation payloads or payload hashes and error traces.
- CloudTrail logging function-management events (CreateFunction, UpdateFunctionCode) and invocation context.
- Inventory of functions, their triggers, IAM roles, and environment variables.
- Baseline of normal invocation rates, durations, and error rates per function.

## Procedure

1. Instrument for injection visibility. Ensure function logs capture: invocation source/trigger, sanitized input characteristics (length, encoding anomalies), execution errors and stack traces (injection often causes distinctive errors before succeeding), and child-process or network activity if the runtime allows. Without input-adjacent telemetry, injection is invisible.
2. Detect injection patterns in invocations. Alert on: payloads containing command-injection metacharacters or known malicious strings, deserialization of unexpected object types, template-injection syntax in inputs, anomalous input sizes or deeply nested structures (DoS precursors), and error-rate spikes correlated with probing patterns (attackers fuzz before succeeding).
3. Watch for post-injection behaviors. Successful injection shows as: the function spawning child processes (unusual for most functions), outbound network connections to rare destinations, access to the metadata/credential endpoint from the function, environment-variable exfiltration (logged or transmitted), and invocation of other AWS/GCP APIs outside the function's normal role scope.
4. Monitor the function supply chain. Alert on: function code/configuration changes outside deployment pipelines (UpdateFunctionCode, layer changes), new function versions published unexpectedly, environment-variable modifications (credential injection), and trigger changes (adding public API Gateway triggers to internal functions). Code-change without a pipeline is a compromise indicator.
5. Correlate with IAM role abuse. Functions assume IAM roles — injection often aims at the role's permissions: alert on the function's role used from unexpected contexts, privilege-escalation patterns (iam:PassRole, new policy attachments), and data-access anomalies (the function suddenly reading unrelated S3 buckets or databases). Scope role permissions to least privilege to bound injection impact.
6. Respond as application compromise: disable or roll back the affected function version, rotate exposed credentials and environment secrets, review CloudTrail for actions taken via the function's role, fix the injection vulnerability (input validation, parameterized execution, updated runtimes), and redeploy through the pipeline. Treat the function's IAM role as compromised until proven otherwise.

## Expected outputs

- Injection detections: malicious-payload patterns, probing/error anomalies, post-injection behavior (child processes, egress, metadata access).
- Function-change monitoring: code/config/trigger/env-var modifications outside pipelines.
- IAM role-abuse correlation for function roles.
- Response runbook: rollback, secret rotation, vulnerability fix, redeployment.

## Pitfalls

- Overly broad payload matching fires on legitimate special characters — tune with allowlists per function input schema.
- Functions legitimately vary in behavior after deployments — baseline per version, not just per function.
- Cold starts and retries create invocation anomalies; distinguish infrastructure noise from attacks.
- Logging full payloads may capture PII — hash or sample payloads under data-handling policy.
- Fixing the alert without fixing the injection vulnerability guarantees recurrence — always remediate the code.

## References

- AWS documentation: Lambda logging, CloudTrail Lambda events; MITRE ATT&CK T1190 (Exploit Public-Facing Application) — https://attack.mitre.org/techniques/T1190/; OWASP Serverless Top 10
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
