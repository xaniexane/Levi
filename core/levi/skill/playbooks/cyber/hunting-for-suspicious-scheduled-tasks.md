---
skill_id: cyber_hunting_for_suspicious_scheduled_tasks
name: Hunting for Suspicious Scheduled Tasks
description: Operational triage guide for suspicious scheduled tasks: anomaly scoring, creation-event correlation, and distinguishing malicious from legitimate tasks.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, triage]
version: 1.0.0
---
## Purpose

A companion to the scheduled-task persistence playbook, this is the
operational triage guide: how to work through a fleet's scheduled-task
inventory efficiently — anomaly scoring, distinguishing the large
legitimate task population from malicious additions, and a disposition
workflow for analysts.

## When to use

- Triaging scheduled-task alerts from SIEM/EDR.
- Working the output of a fleet task inventory collection.
- Building a scheduled-task anomaly-scoring analytic.
- Training analysts on task triage.

## Prerequisites

- Fleet task inventory with parsed XML (actions, triggers,
  principals, authors, creation dates).
- Task-creation events (4698) correlated where available.
- Baselines per host role and software-deployment change records.
- A disposition taxonomy and triage queue.

## Procedure

1. **Score by anomaly features.** Rank tasks on: principal (SYSTEM/
   highest privileges scores higher), action target (unsigned,
   script, encoded), path (temp, user-writable, non-standard),
   author (unexpected), creation date (recent, outside deployments),
   and fleet prevalence (unique to one host scores higher).
2. **Triage the top of the ranked list.** For each high-scoring task,
   examine the full XML: exact command line, triggers, conditions,
   and multiple actions. Many malicious tasks hide intent in
   arguments, not the binary name.
3. **Correlate creation events.** Match tasks to 4698 creation events:
   who/what created it and when. Tasks created by installers during
   deployment windows are usually legitimate; tasks created by script
   hosts or during incident windows are not.
4. **Batch-disposition legitimate patterns.** Group identical tasks
   (same action, trigger, principal) across the fleet and disposition
   the pattern once with justification — OS and vendor tasks collapse
   into a manageable set of known-good patterns.
5. **Investigate the unexplained remainder.** For tasks that cannot be
   tied to legitimate software: analyze the payload, check for hidden
   attributes and COM-handler actions, and look for companion
   persistence on the same host.
6. **Check task history and results.** Review last-run times and exit
   codes — a malicious task that has been running successfully for
   weeks indicates longer dwell than the creation date alone suggests.
   Correlate run times with other incident telemetry.
7. **Escalate with evidence.** Confirmed malicious tasks go to IR with
   the full task XML, creation attribution, payload analysis, and
   observed run history.
8. **Tune the scoring.** Feed dispositions back into the anomaly model:
   promote validated malicious features, demote noisy legitimate
   patterns, and track precision over time.

## Expected outputs

- Ranked task inventory with anomaly scores.
- Pattern-level dispositions with justifications.
- Escalations with full evidence packages.
- A tuned anomaly-scoring analytic with precision tracking.

## Pitfalls

- Alerting on task names — attackers use legitimate-looking names;
   score on actions, principals, and creation context.
- Ignoring disabled tasks — attackers disable rather than delete;
   disabled-but-malicious tasks still indicate compromise.
- Missing tasks created via XML import or COM API that bypass
   schtasks logging — enumerate the store, not just the logs.
- One-off triage without baselines — the same legitimate tasks will
   be re-investigated forever; invest in pattern documentation.
- Forgetting the author field — unexpected authors (users creating
   SYSTEM tasks) are a strong signal.

## References

- MITRE ATT&CK: T1053.005 (Scheduled Task)
- The companion playbook: Hunting for Scheduled Task Persistence
- Microsoft Learn: Task Scheduler schema documentation
- Windows Security auditing documentation (4698 et al.)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
