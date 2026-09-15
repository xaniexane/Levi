---
skill_id: cyber_building_threat_hunt_hypothesis_framework
name: Building a Threat Hunt Hypothesis Framework
description: Practitioner guide to structuring threat-hunting around testable hypotheses instead of aimless log searching.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-hunting, methodology]
version: 1.0.0
---
## Purpose
Effective hunting starts with a question, not a query. This playbook builds a hypothesis-driven hunting framework: generating hypotheses from threat intelligence, scoping them to your environment, testing them against telemetry, and converting results into detections or closed leads. It turns hunting from heroics into a repeatable program.

## When to use
- Starting a threat-hunting program or maturing ad-hoc hunting.
- Focusing hunts on the threats most relevant to the organization.
- Training analysts to hunt systematically rather than randomly.
- Measuring whether hunting actually finds anything.

## Prerequisites
- Telemetry coverage sufficient for the hypotheses (endpoint, network, identity logs).
- Threat-intelligence inputs: actor profiles, recent advisories, industry sharing.
- Hunting time protected from alert-queue duty.
- Documentation space: hunt log or tracking system.

## Procedure
1. Generate hypotheses. Derive them from threat-intel (actors targeting your sector), recent incidents, new ATT&CK techniques, or control gaps; write each as a falsifiable statement.
2. Prioritize. Score hypotheses by likelihood, potential impact, and data availability; hunt the high-value ones first.
3. Scope the hunt. Define the systems, time window, and data sources; confirm the needed telemetry actually exists before starting.
4. Build the test. Translate the hypothesis into queries and checks; document exactly what would confirm or refute it.
5. Execute and record. Run the hunt, logging every query and observation so the work is reproducible and reviewable.
6. Adjudicate. Mark the hypothesis confirmed, refuted, or inconclusive; for confirmed hunts, open incidents; for refuted ones, record the evidence.
7. Convert findings to detections. Turn successful hunt logic into permanent detection rules with runbooks.
8. Review the program. Track hunt throughput, confirmation rate, and detection conversions; retire hypothesis sources that never produce.

## Expected outputs
- Hypothesis backlog with prioritization criteria.
- Hunt log with reproducible queries and adjudications.
- New or improved detections derived from hunts.

## Pitfalls
- Hunting without hypotheses becomes expensive log browsing.
- Hypotheses that the available telemetry cannot test waste analyst time; check data first.
- Unrecorded hunts cannot be reviewed, repeated, or converted to detections.
- Never closing inconclusive hunts leaves an ever-growing backlog.

## References
- MITRE ATT&CK for technique-based hypothesis generation
- Sqrrl (now Amazon) threat-hunting maturity model concepts
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- SANS FOR508 hunting methodology concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
