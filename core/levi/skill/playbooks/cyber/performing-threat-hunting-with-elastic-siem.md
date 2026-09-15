---
skill_id: cyber_performing_threat_hunting_with_elastic_siem
name: Threat Hunting with Elastic SIEM
description: Hunt for threats in Elastic SIEM with hypothesis-driven queries across endpoint, network, and cloud data.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, elastic, siem]
version: 1.0.0
---

## Purpose
- Find threats that evaded automated detections through analyst-driven hunting.
- Turn threat intelligence into concrete hunt hypotheses and queries.
- Build a library of hunts the team can rerun as new data arrives.

## When to use
- On a regular hunt cadence, typically weekly, driven by current threat intelligence.
- After incidents, to find related activity the initial investigation missed.
- When new log sources come online and their normal baseline is unknown.
- When validating that high-risk techniques would be visible in current telemetry.

## Prerequisites
- Elastic SIEM with relevant data sources onboarded: endpoint, network, identity, and cloud.
- Threat intelligence feeds or reports to drive hypotheses.
- Hunt tracking: hypotheses, queries, results, and follow-ups recorded consistently.
- Baseline familiarity with normal activity in the environment.

## Procedure
1. Select a hunt hypothesis from threat intelligence, past incidents, or MITRE ATT&CK technique analysis.
2. Define what evidence the hypothesis would leave in available data sources.
3. Write the initial broad query in EQL or Kibana Query Language, then narrow iteratively.
4. Establish the baseline: what does normal look like for the entities in the result set.
5. Investigate anomalies: pivot on hosts, users, processes, and time windows.
6. Distinguish benign explanations from malicious activity with additional context.
7. For confirmed findings, escalate through the incident response process with full evidence.
8. For benign anomalies, document them as known-good to speed future hunts.
9. Save successful hunts as detection rules or scheduled queries where appropriate.
10. Record the hunt: hypothesis, queries, data reviewed, conclusion, and time spent.
11. Review hunt metrics: findings per hunt hour and coverage of the threat model.
12. Share sanitized hunt techniques with the wider team.

## Expected outputs
- Hunt reports with hypotheses, methods, and conclusions.
- New detections promoted from successful hunts.
- A hunt library with documented baselines.
- A hunt calendar aligned with threat-intel releases and industry alerts.
- Dashboards tracking hunt coverage against the ATT&CK matrix.

## Pitfalls
- Hunting without a hypothesis; aimless querying wastes time and misses threats.
- Ignoring the baseline; every environment has benign weirdness that looks malicious.
- Never converting hunts to detections; the same hunt should not require manual effort forever.
- Hunting in data with unknown retention gaps; verify coverage first.

## References
- Elastic detection rules repository for promotion candidates
- Elastic SIEM documentation
- MITRE ATT&CK for hypothesis development, https://attack.mitre.org/
- SANS FOR508 threat hunting methodology
- TaHiTI threat hunting methodology
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
