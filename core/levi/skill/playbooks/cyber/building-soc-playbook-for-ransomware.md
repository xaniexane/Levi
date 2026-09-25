---
skill_id: cyber_building_soc_playbook_for_ransomware
name: Building a SOC Playbook for Ransomware
description: Practitioner guide to an analyst-level SOC runbook for detecting, triaging, and containing ransomware in its first minutes.
risk: info
permissions: []
requires_confirmation: false
tags: [soc, incident-response, ransomware]
version: 1.0.0
---
## Purpose
Ransomware spreads in minutes, so the SOC needs a runbook, not a policy document: which alerts matter, what to check first, how to isolate, and when to declare an incident. This playbook gives Tier 1 and Tier 2 analysts a concrete, fast procedure aligned with the organization's broader ransomware plan.

## When to use
- Giving SOC analysts a concrete ransomware response procedure.
- Reducing time from first ransomware indicator to containment.
- Training new analysts on ransomware triage.
- Exercising the SOC's ransomware readiness.

## Prerequisites
- Aligned organizational ransomware playbook and escalation contacts.
- EDR with host-isolation capability and tested network-isolation procedures.
- Backup status visibility so analysts know what recovery options exist.
- Pre-authorization for emergency isolation actions.

## Procedure
1. Recognize the triggers. Memorize the high-confidence indicators: mass file modification, shadow-copy deletion, EDR tampering, ransom notes, and backup-repository anomalies.
2. Triage in the first five minutes. Confirm the alert is real, identify the affected host and user, and check for lateral-movement indicators to other hosts.
3. Isolate immediately. Quarantine the affected host from the network (keeping it powered on for forensics); expand isolation if additional hosts show indicators.
4. Preserve evidence. Capture volatile data and secure logs before containment actions overwrite them; note the ransom note contents without interacting with payment demands.
5. Escalate per the matrix. Declare the incident at the defined severity, notify the incident commander, and hand off with a structured summary.
6. Hunt for spread. Search for the same indicators across the fleet: file hashes, ransom-note filenames, and the initial-access vector.
7. Support eradication. Assist IR with identifying patient zero, the entry vector, and persistence; do not rebuild systems yourself.
8. Document everything. Log times, actions, and observations in the ticket; this record feeds the post-incident review.

## Expected outputs
- Analyst ransomware runbook with triggers, first-five-minute checks, and isolation steps.
- Pre-authorized containment actions and escalation contacts.
- Ticketing templates for ransomware incidents.

## Pitfalls
- Waiting for certainty before isolating lets ransomware spread; act on high-confidence indicators.
- Powering off hosts destroys volatile evidence; isolate, don't shut down.
- Analysts rebuilding machines themselves breaks chain of custody and may miss persistence.
- Interacting with ransom demands without legal and leadership involvement.

## References
- CISA: Stop Ransomware guide
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- MITRE ATT&CK: T1486 (Data Encrypted for Impact)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
