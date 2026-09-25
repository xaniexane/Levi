---
skill_id: cyber_detecting_malicious_scheduled_tasks_with_sysmon
name: Detecting Malicious Scheduled Tasks with Sysmon
description: Detect attacker persistence via Windows scheduled tasks using Sysmon telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [sysmon, persistence, windows]
version: 1.0.0
---
## Purpose

Scheduled tasks are a favorite persistence mechanism: they survive reboots, run as SYSTEM, and blend into the hundreds of legitimate tasks on any Windows host. This playbook uses Sysmon (and Security log) telemetry to separate attacker-created tasks from the noise — focusing on creation events, suspicious actions, and the parent processes that reveal malicious intent.

## When to use

- You need persistence-detection coverage for Windows endpoints.
- Threat hunting for a suspected intrusion's foothold mechanism.
- EDR flagged schtasks.exe or task creation and you need a triage procedure.
- Validating that red-team/purple-team persistence was caught by your rules.

## Prerequisites

- Sysmon deployed with a configuration capturing process creation (Event ID 1), file creation (11), and registry events (12/13/14); Security log Task Scheduler operational events help (Microsoft-Windows-TaskScheduler/Operational, IDs 106/140/141).
- Centralized collection of Sysmon and TaskScheduler logs.
- Baseline of legitimate task-creation sources: SCCM, GPO, software installers, admin scripts.
- Knowledge of normal task paths and principals (SYSTEM tasks created by installers vs. user tasks).

## Procedure

1. Collect the right events. Ensure you capture: process creation for schtasks.exe and task-related COM activity, TaskScheduler Operational log events 106 (task registered), 140/141 (task updated/deleted), and file/registry writes under task storage paths. Confirm the Operational log is enabled and forwarded — it is off or unforwarded in many environments.
2. Alert on task creation with suspicious characteristics: tasks whose actions point to user-writable directories (AppData, Temp, Downloads), tasks executing scripts/interpreters (powershell, wscript, mshta) with encoded or URL arguments, tasks with deliberately misleading names mimicking system tasks, and tasks created with highest privileges or SYSTEM principal by non-admin processes.
3. Weight the parent process heavily. Legitimate task creation comes from installers, SCCM agents, and admin tools. Task registration spawned by Office applications, browsers, script interpreters, or LOLBins is high-confidence malicious until proven otherwise — make parent/child the primary triage field.
4. Hunt for timestomping and concealment. Check for tasks with creation times inconsistent with their registration events, tasks hidden via registry manipulation, XML task definitions dropped directly to disk, and tasks whose actions were modified after creation (event 141 followed by re-registration).
5. Correlate with the broader intrusion. A malicious scheduled task rarely stands alone: look for the initial-access vector (phishing, exploitation) and concurrent persistence (registry run keys, services, WMI) on the same host and timeline. Scope to other hosts for the same task name/action hash.
6. Respond with persistence-removal discipline. Disable (don't just delete) the task first to preserve evidence, capture the task XML and the payload it executes, remove all related persistence, then remediate the host. Deleting the task while leaving the dropper guarantees re-infection.

## Expected outputs

- Sysmon + TaskScheduler detection rules for malicious task registration, with parent-process weighting.
- Triage runbook: task XML capture, payload analysis, related-persistence checklist.
- Baseline of legitimate task-creation sources with exclusions documented.
- Purple-team validation record showing test persistence was detected.

## Pitfalls

- The TaskScheduler Operational log is not forwarded by default in many setups — verify before relying on it.
- Software installers create tasks constantly; alerting on all registrations without parent baselining is unusable.
- Attackers register tasks via COM API without schtasks.exe — process-only detection misses these; the Operational log catches them.
- Deleting a malicious task before capturing its XML and payload destroys evidence of the full chain.
- Task names are attacker-controlled; match on action paths, principals, and parents — not names.

## References

- Microsoft Learn: Task Scheduler event logging; MITRE ATT&CK T1053.005 (Scheduled Task/Job: Scheduled Task) — https://attack.mitre.org/techniques/T1053/005/; Sysmon documentation (Event IDs 1, 11, 12-14)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
