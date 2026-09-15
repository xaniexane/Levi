---
skill_id: cyber_implementing_web_application_logging_with_modsecurity
name: Implementing Web Application Logging with ModSecurity
description: Deploy ModSecurity for high-fidelity web application logging and attack visibility.
risk: low
permissions: []
requires_confirmation: false
tags: [waf, web-security, logging]
version: 1.0.0
---
## Purpose
This playbook deploys ModSecurity (with the OWASP Core Rule Set) primarily as a visibility and detection layer: rich request/response logging, anomaly scoring, and tuned blocking — giving defenders ground truth about web attacks against their applications.

## When to use
- Web attacks are invisible: the application logs status 200 but nobody sees the payloads.
- You need WAF-grade telemetry feeding the SIEM for detection engineering.
- Preparing to move from detection-only to blocking mode safely.

## Prerequisites
- Reverse proxy or web server layer where ModSecurity can be embedded (nginx/Apache) with capacity for inspection overhead.
- OWASP Core Rule Set (CRS) version pinned and a change process for rule updates.
- SIEM ingestion ready for the JSON audit log format.

## Procedure
1. **Deploy in detection-only mode.** Start with `SecRuleEngine DetectionOnly` and the CRS in anomaly-scoring mode; collect at least two weeks of production traffic.
2. **Ship structured audit logs.** Enable the JSON audit log format with request headers, matched rules, anomaly scores, and (carefully) request bodies; forward to the SIEM.
3. **Tune out false positives.** Build exclusion rules per application endpoint based on observed legitimate traffic; document each exclusion with justification and review date.
4. **Build SIEM detections.** Alert on high anomaly scores, repeated rule triggers from single sources, and CRS rule IDs mapped to ATT&CK techniques (e.g., SQLi, RCE patterns).
5. **Promote to blocking in stages.** Enable blocking per paranoia level or per rule group after false-positive rates are acceptable; keep a fast rollback path.
6. **Protect the logs themselves.** Redact or mask sensitive fields (passwords, tokens, PII) in audit logs before they reach long-term storage.
7. **Maintain the rule set.** Update CRS on a schedule, re-run tuning after application changes, and review exclusions quarterly.

## Expected outputs
- ModSecurity deployed with tuned CRS, structured audit logging to SIEM.
- Exclusion register with justifications and review dates.
- SIEM detections for web attack classes with measured false-positive rates.

## Pitfalls
- Enabling blocking on day one: legitimate traffic gets dropped and the WAF gets disabled in anger.
- Logging full request bodies without redaction, creating a PII honeypot in the SIEM.
- Tuning exclusions so broad they neuter the rules they were meant to refine.

## References
- ModSecurity and OWASP Core Rule Set documentation (owasp.org/www-project-modsecurity-core-rule-set).
- NIST SP 800-95, Guide to Secure Web Services.
