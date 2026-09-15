---
skill_id: cyber_detecting_sql_injection_via_waf_logs
name: Detecting SQL Injection via WAF Logs
description: Detect SQL injection attempts and successes in WAF and application logs.
risk: low
permissions: []
requires_confirmation: false
tags: [waf, sqli, detection]
version: 1.0.0
---
## Purpose

SQL injection remains a top web-application risk, and WAF logs are often the first place attempts appear. This playbook shows defenders how to detect SQLi from WAF telemetry: tuning signatures beyond defaults, distinguishing probing from exploitation, correlating with application logs to find successes, and feeding findings back to developers.

## When to use

- You have a WAF and need SQLi-specific detection use cases.
- WAF SQLi alerts are noisy or, worse, silent during testing.
- A penetration test or bug bounty found SQLi — check for prior exploitation.
- Building application-layer detection to complement WAF blocking.

## Prerequisites

- WAF logs with full request details (or at least matched-rule data, URIs, and parameters) in your SIEM.
- Application/database logs: web-server access logs, application error logs, DB slow-query or audit logs.
- Inventory of applications behind the WAF and their normal parameter patterns.
- WAF in blocking or detection mode — know which, per application.

## Procedure

1. Verify what your WAF actually inspects. Confirm: which parts of requests are inspected (query params, body, headers, JSON payloads), whether the WAF decrypts TLS itself or relies on upstream termination, and rule-set currency. SQLi in JSON bodies or headers bypasses WAFs configured for form-params only — close the inspection gaps before tuning signatures.
2. Tune SQLi signatures past defaults. Default rule sets catch `' OR 1=1` but miss: stacked queries, time-based blind payloads (SLEEP/BENCHMARK/WAITFOR patterns), out-of-band exfiltration, and encoded/obfuscated payloads (double encoding, comment obfuscation). Add custom rules for your application's parameter context — a numeric ID parameter receiving SQL keywords is always suspicious — and test with both attack payloads and legitimate traffic.
3. Distinguish probing from exploitation. Probing: single quotes, boolean logic tests, error-inducing inputs scattered across parameters — low severity, high volume. Exploitation: UNION SELECT with column enumeration, time-based delays correlating with response times, OOB callbacks to attacker infrastructure, and successful data-extraction patterns. Build severity tiers on this distinction and alert accordingly.
4. Correlate WAF alerts with application/database logs — this finds successes. Join WAF SQLi alerts with: application error logs (database error messages leaking schema info), DB audit logs showing unusual queries from the app account (e.g., SELECTs against tables the app never touches), and response-size anomalies (large responses following injection attempts). A WAF 'blocked' alert followed by DB evidence of extraction means the WAF missed it — investigate immediately.
5. Hunt historically on confirmed findings. When SQLi is confirmed in one application: search WAF history for the attacker's IP/infrastructure across all applications, check for prior successful exploitation (DB logs, data-access anomalies), and assess data exposure for notification obligations. Attackers retest; defenders should re-hunt.
6. Feed findings to development as defects, not just blocks. Every confirmed SQLi attempt pattern becomes: a ticket for parameterized queries/prepared statements, input-validation improvements, least-privilege DB accounts, and regression tests. WAF rules are compensating controls — the fix is in the code. Track remediation to closure.

## Expected outputs

- SQLi WAF rules: tuned signatures per application parameter context, with probing/exploitation severity tiers.
- WAF↔app↔DB correlation queries for detecting successful exploitation.
- Historical hunt procedure for confirmed SQLi findings.
- Developer remediation backlog: parameterized queries, DB least privilege, regression tests.

## Pitfalls

- WAFs in detection-only mode log but don't stop — know your mode per app.
- Signature-only detection misses blind/time-based SQLi — correlate with DB behavior and timing.
- Blocking on SQL keywords breaks legitimate inputs (e.g., a surname 'O'Brien') — context-aware rules, not keyword bans.
- Attackers rotate IPs; infrastructure-pattern hunting (payloads, timing, targets) outlasts IP blocks.
- A WAF 'blocked' log is not proof of safety — verify with application-layer evidence.

## References

- OWASP SQL Injection guidance and Testing Guide; MITRE ATT&CK T1190 (Exploit Public-Facing Application) — https://attack.mitre.org/techniques/T1190/; WAF vendor documentation for custom rule syntax
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
