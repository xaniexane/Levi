---
skill_id: cyber_implementing_siem_use_cases_for_detection
name: Implementing SIEM Use Cases for Detection
description: Design, build, and validate SIEM detection use cases mapped to adversary behaviors.
risk: low
permissions: []
requires_confirmation: false
tags: [siem, detection-engineering, use-cases]
version: 1.0.0
---
## Purpose
This playbook guides a security team through building a repeatable pipeline for SIEM detection use cases: selecting behaviors to detect, engineering the logic, testing it, and measuring its operational value. It applies to any SIEM (Splunk, Elastic, Sentinel, Chronicle) because it focuses on process rather than vendor syntax.

## When to use
- Standing up a new SIEM or maturing an existing deployment.
- Reducing alert noise while improving coverage of high-priority threats.
- Preparing for audits that ask how detections map to frameworks such as MITRE ATT&CK.
- After an incident, when a post-mortem identifies a detection gap to close.

## Prerequisites
- A populated asset inventory and a threat model or recent risk assessment.
- Log sources onboarding with documented field mappings (CIM, ECS, or ASIM normalization).
- Read access to the SIEM for development and a non-production search environment for testing.
- Baseline metrics: current alert volume, true/false positive rates, mean time to triage.

## Procedure
1. **Prioritize with a coverage matrix.** Map candidate detections to MITRE ATT&CK techniques relevant to your threat model. Score each by adversary likelihood, business impact, and log availability.
2. **Write the use-case record.** For each selected detection, document: title, MITRE technique ID, data sources, hypothesis, logic in plain language, severity, expected volume, and the triage runbook it links to.
3. **Prototype in a dev search.** Build the query against historical data first. Tune thresholds using at least 30 days of history so you know the baseline volume before it ever pages anyone.
4. **Add context enrichment.** Join the alert with asset criticality, identity risk, and threat intelligence matches so analysts get a verdict-ready event, not a raw log line.
5. **Define the response.** Attach a triage checklist: what to confirm, what to contain, escalation criteria, and expected SLA. A detection without a response plan is just noise.
6. **Deploy with a canary phase.** Enable in monitor-only mode for one to two weeks. Review every firing, adjust logic, and only then route to the on-call queue.
7. **Measure and review quarterly.** Track precision (true positives / total), coverage against the ATT&CK matrix, and time-to-detect. Retire or rewrite use cases that chronically false-positive.
8. **Version-control everything.** Store detection logic as code (Sigma rules, saved searches in git) with change history and peer review, the same as application code.

9. **Red-team the detections.** Have a purple-team exercise attempt the covered techniques and confirm each use case fires; a detection that has never fired on real adversary behavior is unproven.
10. **Document data dependencies.** For each use case, record the exact log sources and fields it needs, and alert when a source stops flowing — silent log loss is the most common detection killer.

## Expected outputs
- A catalog of documented, ATT&CK-mapped detection use cases with owners and review dates.
- Detection-as-code repository with peer-reviewed, tested logic.
- Metrics: detection coverage per tactic, alert precision, MTTD per use case.
- Triage runbooks linked one-to-one with production detections.
- Example: a "Suspicious PowerShell EncodedCommand" use case record showing the Sigma rule, the 30-day baseline volume (e.g., 12 events/day, 0 false positives after tuning), and the linked containment runbook.

## Pitfalls
- Writing detections for log sources that are not reliably onboarded; missing logs silently disable logic.
- Optimizing for coverage count over quality: 200 noisy rules are worse than 40 precise ones.
- Skipping the canary phase and paging analysts with untested logic, which burns out the SOC.
- Treating detections as write-once: adversary behavior and your environment both change, so schedule reviews.

- Copying detections from another organization without re-baselining: their normal is not your normal, and the thresholds will be wrong on day one.
- Letting detection ownership default to "the SOC": every use case needs a named engineer who understands both the logic and the data source.

## References
- MITRE ATT&CK framework (attack.mitre.org) — technique and tactic reference.
- Sigma rule specification (github.com/SigmaHQ/sigma) — vendor-neutral detection format.
- NIST SP 800-92, Guide to Computer Security Log Management.
- SANS SEC555 / SIEM architecture course materials (sans.org) — detection engineering practices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
