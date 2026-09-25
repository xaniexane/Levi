---
skill_id: cyber_detecting_insider_threat_with_ueba
name: Detecting Insider Threat with UEBA
description: Detect anomalous user and entity behavior indicative of insider threats using UEBA analytics.
risk: low
permissions: []
requires_confirmation: false
tags: [insider-threat, ueba, detection]
version: 1.0.0
---
## Purpose

Insider threats succeed because the actor already has legitimate access, so signature-based controls rarely fire. This playbook describes how defenders use User and Entity Behavior Analytics (UEBA) to baseline normal activity and surface high-risk deviations — data hoarding before resignation, off-hours access spikes, impossible-travel logons — so the SOC can investigate before exfiltration or sabotage completes.

## When to use

- HR flags a resignation, termination, or performance action and you need to assess data-access risk.
- An employee's access pattern changes abruptly (new hours, new systems, new volumes).
- DLP or CASB alerts suggest bulk downloads but the source is an authorized account.
- Building a proactive insider-threat hunting program rather than reacting to incidents.
- Reviewing whether privileged users' behavior matches their role baseline.

## Prerequisites

- A UEBA platform (or SIEM with behavioral analytics) ingesting identity, endpoint, and cloud logs with at least 30-90 days of history.
- HR/legal-approved insider-threat policy defining what may be monitored, retention, and escalation paths; involve legal and HR before acting on any finding.
- Identity data joined across sources: usernames, service accounts, and cloud identities mapped to people.
- Baseline knowledge of role-based access norms (finance vs. engineering vs. executives differ legitimately).

## Procedure

1. Establish per-entity baselines first. Confirm the UEBA model has learned normal logon times, accessed resources, data volumes, and peer-group behavior for the population you will monitor. Models trained on less than a full business cycle (including quarter-end, release windows) generate noise — validate the baseline period before trusting alerts.
2. Prioritize high-risk scenarios over raw anomaly scores. Tune or build use cases for: mass download/copy to removable media or personal cloud storage, access to repositories outside the user's role, first-time access to crown-jewel systems, logons at unusual hours or from unusual locations, and email forwarding rules to external addresses.
3. Correlate UEBA risk scores with HR context. A spike in exfiltration-like behavior the week before a resignation is materially different from the same spike during a reorg-driven data migration. Work with HR through the approved process — never freelance HR data.
4. Investigate top-risk entities with supporting telemetry. For each flagged user, pull: full authentication timeline, file-access and DLP events, endpoint process activity, email/web gateway logs, and badge/physical access if available. Build a timeline before drawing conclusions.
5. Distinguish malicious intent from policy drift. Many 'anomalies' are legitimate: an engineer bulk-downloading a repo before a flight, finance pulling quarter-end reports. Confirm business justification with the user's manager through the formal process before escalating.
6. Escalate through the insider-threat workflow. Confirmed malicious or high-risk cases go to HR, legal, and physical security per policy — the SOC should not confront employees. Preserve evidence with chain of custody in case of legal action.
7. Measure and tune. Track true/false positive rates per use case, time-to-investigation, and whether peer-group analytics outperform individual baselines. Retire or re-tune use cases that only produce noise.

## Expected outputs

- Documented UEBA use cases with baselines, thresholds, and expected true-positive rates.
- Investigation timelines for reviewed entities, with disposition (benign / policy violation / malicious).
- Tuned alert rules and a quarterly review record with HR/legal.
- Metrics: alerts per use case, investigation time, confirmed insider cases, false-positive rate.

## Pitfalls

- UEBA without HR context produces witch hunts — anomaly is not intent, and most anomalies are benign.
- Short baselines (under a full business cycle) flag every quarter-end and release as anomalous.
- Service accounts and shared accounts poison user baselines; exclude or separately model non-human identities.
- Monitoring employees without a documented, legally reviewed policy creates employment-law exposure — get the policy first.
- Tunnel vision on exfiltration misses sabotage: watch for mass deletions, permission changes, and logic-bomb indicators too.

## References

- NIST SP 800-53 (AU, PE, PM families) — insider threat controls; Carnegie Mellon SEI Common Sense Guide to Mitigating Insider Threats; MITRE ATT&CK T1530 (Data from Cloud Storage), T1039 (Data from Network Shared Drive), T1114 (Email Collection) — https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
