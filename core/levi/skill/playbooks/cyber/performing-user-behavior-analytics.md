---
skill_id: cyber_performing_user_behavior_analytics
name: User Behavior Analytics
description: Deploy user behavior analytics to detect insider threats, compromised accounts, and policy violations.
risk: low
permissions: []
requires_confirmation: false
tags: [uba, insider-threat, detection]
version: 1.0.0
---

## Purpose
- Detect malicious or risky user behavior that signature-based controls miss.
- Catch compromised accounts through behavioral anomalies before damage spreads.
- Give insider-threat programs a data-driven foundation with privacy safeguards.

## When to use
- When building insider-threat or compromised-account detection capability.
- After incidents where legitimate credentials were abused.
- When data-loss patterns suggest behavioral rather than technical gaps.
- As a complement to DLP and EDR in a layered detection strategy.

## Prerequisites
- Legal, HR, and privacy review of monitoring scope, especially in regulated jurisdictions.
- Data sources: authentication logs, endpoint activity, file access, email, and cloud audit logs.
- A baseline period to train behavioral models on normal activity.
- Defined response workflows for the alert types UBA will generate.

## Procedure
1. Get written approval defining monitored populations, data sources, and retention limits.
2. Onboard data sources with quality checks; UBA is only as good as its inputs.
3. Allow a baseline learning period, typically 30 days, before trusting anomaly scores.
4. Tune risk models to the organization: peer groups, roles, and known benign anomalies.
5. Define use cases: impossible travel, off-hours access spikes, mass downloads, and privilege misuse.
6. Build investigation playbooks for each use case with HR and legal involvement points.
7. Triage alerts with context: role changes, travel, and projects explain many anomalies.
8. Escalate confirmed malicious behavior through the insider-threat or IR process with evidence packages.
9. Protect privacy: limit who sees raw user activity and audit analyst access.
10. Measure effectiveness: true positive rates, time to detection, and analyst workload.
11. Review and retune models quarterly as roles, tools, and work patterns change.
12. Report trends to leadership without turning metrics into surveillance theater.

## Expected outputs
- Operational UBA use cases with tuned models and baselines.
- Investigation playbooks with HR and legal integration.
- Effectiveness metrics and quarterly tuning records.
- A UBA governance document covering scope, retention, and oversight.
- Regular access reviews of who can view UBA findings.

## Pitfalls
- Deploying without legal and HR alignment; UBA programs die on privacy challenges.
- Alerting on every anomaly; without tuning, analysts drown and real threats hide in noise.
- Using UBA scores punitively without investigation; behavior models are leads, not verdicts.
- Expanding monitoring scope without renewed legal review.

## References
- NIST SP 800-53 control AU-6 on audit review and analysis
- NIST SP 800-53 controls on audit and anomaly detection
- CERT insider threat research from Carnegie Mellon SEI
- Vendor UBA documentation for the platform in use
- Applicable employee monitoring laws for operating jurisdictions
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
