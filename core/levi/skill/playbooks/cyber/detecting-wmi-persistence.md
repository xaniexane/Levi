---
skill_id: cyber_detecting_wmi_persistence
name: Detecting WMI Persistence
description: Detect attacker persistence via WMI event subscriptions and consumers.
risk: low
permissions: []
requires_confirmation: false
tags: [wmi, persistence, windows]
version: 1.0.0
---
## Purpose

WMI event-subscription persistence — a filter, consumer, and binding that triggers malicious actions on system events — is fileless, survives reboots, and is invisible to Autoruns-style checks that only look at common locations. This playbook covers detecting malicious WMI persistence using WMI repository inspection, Sysmon, and Security-log telemetry.

## When to use

- You need persistence-detection coverage beyond run keys and scheduled tasks.
- Threat hunting for fileless persistence after an intrusion.
- EDR flagged WMI activity and you need a triage procedure.
- Validating that purple-team WMI persistence was detected.

## Prerequisites

- Sysmon with WMI event capture (Event IDs 19, 20, 21 — WmiEventFilter/Consumer/Binding activity) enabled in config.
- Ability to query the WMI repository: PowerShell (Get-WMIObject __EventFilter/__EventConsumer/__FilterToConsumerBinding) or WMI Explorer tooling.
- Baseline of legitimate WMI subscriptions: SCCM, monitoring agents, and management tools create these legitimately.
- Security log process-creation (4688) or Sysmon Event 1 for wmic/powershell WMI activity.

## Procedure

1. Enable Sysmon WMI telemetry. Confirm your Sysmon configuration captures Event IDs 19, 20, and 21 — many default configs don't. These events fire when WMI filters, consumers, and bindings are created, giving you real-time detection of persistence installation. Without them you're limited to periodic repository scans, which miss short-lived subscriptions.
2. Establish the legitimate-subscription baseline. Enumerate existing WMI event subscriptions across representative hosts: record filter queries, consumer types (CommandLine, ActiveScript), and the actions they trigger. SCCM, monitoring agents, and some management tools create legitimate subscriptions — document them by namespace, query, and consumer so malicious ones stand out.
3. Alert on suspicious subscription characteristics. Flag new subscriptions where: the consumer executes command lines (especially encoded PowerShell, LOLBins, or URLs), the filter query is generic (e.g., triggers every N seconds — timer-based persistence), the subscription lives in non-standard namespaces, or the creating process was Office, a browser, or a script interpreter. Timer-based CommandLine consumers are the classic malicious pattern.
4. Hunt the repository directly and periodically. Even with Sysmon, run scheduled scans: enumerate __EventFilter, __EventConsumer, and __FilterToConsumerBinding in root\subscription across the fleet, diff against the baseline, and investigate new entries. Attackers sometimes install subscriptions during gaps in telemetry — repository scans catch what real-time monitoring missed.
5. Correlate with the intrusion timeline. WMI persistence is installed after initial access: for each malicious subscription, find the creating process and its parent chain, determine the initial-access vector, and check for companion persistence (scheduled tasks, registry, services). WMI subscriptions often come in sets — find all three components (filter, consumer, binding) before declaring the host clean.
6. Remove with completeness. Delete the binding first, then the consumer, then the filter (removing in the wrong order can leave orphans), capture the consumer's command line/payload for analysis, and verify removal by re-enumerating. Then remediate the host: the subscription was the persistence, not the intrusion — find and close the initial access vector.

## Expected outputs

- Sysmon WMI events (19/20/21) enabled and centralized.
- Legitimate-subscription baseline per host role.
- Scheduled repository-scan procedure with baseline diffing.
- Removal procedure: binding → consumer → filter, with verification.

## Pitfalls

- Many Sysmon configs don't capture Events 19-21 by default — verify before assuming coverage.
- Legitimate management tools create WMI subscriptions — baseline before alerting.
- Removing only the consumer while leaving the filter/binding creates orphans and confusion — remove all three.
- Repository scans alone miss short-lived subscriptions — pair with real-time Sysmon events.
- WMI persistence often pairs with other mechanisms — check the full persistence set.

## References

- Microsoft Learn: WMI event subscriptions, Sysmon WMI events; MITRE ATT&CK T1546.003 (Event Triggered Execution: WMI Event Subscription) — https://attack.mitre.org/techniques/T1546/003/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
