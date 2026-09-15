---
skill_id: cyber_hunting_for_scheduled_task_persistence
name: Hunting for Scheduled Task Persistence
description: Detect malicious scheduled tasks: rogue task creation, hidden tasks, COM-handler hijacks, and anomalous triggers/actions.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

Scheduled tasks are a top-tier Windows persistence mechanism: they run as
SYSTEM, support varied triggers, and hide in a large legitimate task
population. This playbook covers hunting malicious tasks — rogue
creations, hidden tasks, and task-com-handler hijacks — in the Task
Scheduler store and event logs.

## When to use

- Post-compromise persistence sweeps.
- Investigating EDR alerts for task creation (4698, Sysmon-adjacent
  telemetry).
- Hunting for persistence on servers where tasks run as SYSTEM.
- Validating task-inventory monitoring coverage.

## Prerequisites

- Task inventory collection across the fleet (schtasks / PowerShell
  enumeration, EDR, or Velociraptor artifacts) including hidden tasks.
- Security log events 4698 (task created), 4699 (deleted), 4700/4701
  (enabled/disabled), 4702 (updated).
- Baseline of legitimate tasks per host role (OS, management agents,
  software updaters create many).
- Ability to read task XML definitions (actions, triggers, principals).

## Procedure

1. **Enumerate all tasks including hidden ones.** Standard listings
   miss hidden tasks — enumerate via the Task Scheduler COM API or
   forensic parsing of the task store (`C:\Windows\System32\Tasks` and
   the registry `TaskCache`) to catch tasks with the hidden attribute.
2. **Parse actions, triggers, and principals.** For each task record the
   executed command (full arguments), triggers (logon, schedule, event,
   idle), and the principal it runs as. SYSTEM-running tasks with
   network or script actions are the highest-risk population.
3. **Diff against baselines.** Compare to role baselines and fleet
   prevalence. Flag tasks with: unsigned or unusual executables,
   obfuscated/encoded arguments, execution from temp or user-writable
   paths, triggers outside maintenance patterns, and recent creation
   dates inconsistent with software deployment.
4. **Hunt creation events.** Query 4698 events for task creation outside
   change windows; correlate the creator (subject user/process) —
   tasks created by script hosts, LOLBins, or compromised users are
   high priority. Watch for 4699 deletions that may indicate
   anti-forensics.
5. **Check for COM-handler and hijack variants.** Review tasks using
   COM-handler actions (`{...}` CLSID actions) and verify the handler
   is legitimate — attackers hijack task COM handlers as a stealthier
   variant. Also check for tasks masquerading with Microsoft-like
   names in non-standard paths.
6. **Validate the payload.** For suspicious tasks, analyze the target
   binary/script: signer, hash reputation, and behavior. A legitimate
   binary with malicious arguments is still malicious — read the full
   action definition.
7. **Remediate completely.** Disable and delete malicious tasks, remove
   payloads, and verify via re-enumeration (including hidden-task
   enumeration). Check for companion persistence mechanisms.
8. **Monitor task creation.** Deploy alerting on 4698 events outside
   change windows and on new SYSTEM-principal tasks; integrate with
   deployment records to auto-explain legitimate additions.

## Expected outputs

- Full task inventories (including hidden) with baseline diffs.
- Triaged suspicious tasks with action/trigger/principal analysis.
- Creation-event correlation with attribution.
- Verified remediation records.
- Task-creation monitoring rules.

## Pitfalls

- Standard `schtasks /query` misses hidden tasks — use COM-API or
   forensic enumeration.
- Legitimate software creates a huge task population — baselining and
   change-record integration are essential.
- Task XML in the registry TaskCache can be tampered to hide from
   API enumeration — for high-assurance cases, parse the files.
- Deleting the task but leaving the payload (or scheduled re-creation
   via another mechanism) — verify holistically.
- 4698 events require the right audit subcategories — verify
   collection before relying on creation-event hunting.

## References

- MITRE ATT&CK: T1053.005 (Scheduled Task)
- Microsoft Learn: Task Scheduler schema and security documentation
- Sysmon and Windows Security auditing documentation (4698 et al.)
- Forensic references for Task Scheduler artifact parsing
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
