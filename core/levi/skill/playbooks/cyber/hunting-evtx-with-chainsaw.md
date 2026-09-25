---
skill_id: cyber_hunting_evtx_with_chainsaw
name: Hunting EVTX with Chainsaw
description: Rapidly triage Windows event logs with Chainsaw: hunt rules, Sigma support, and output workflows for incident response.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, windows, forensics]
version: 1.0.0
---
## Purpose

Chainsaw is a fast, Rust-based tool for hunting through Windows event
logs using built-in hunt rules and Sigma rule support. This playbook
covers using Chainsaw for rapid EVTX triage during incidents: running
hunts, interpreting output, and integrating results into the
investigation workflow.

## When to use

- Rapid triage of collected EVTX files when you need answers in minutes.
- Hunting for specific TTPs (lateral movement, persistence, credential
  access) across historical host logs.
- Validating Sigma rules against real log data before SIEM deployment.
- DFIR training on Windows event-log analysis.

## Prerequisites

- Collected EVTX files from hosts in scope (analyze copies on an
  analysis workstation, never the live host).
- A current Chainsaw build with updated hunt rules and Sigma rule sets.
- Mapping of your log channels to rule requirements (some rules need
  Sysmon or PowerShell logging enabled).
- Hunt hypotheses or incident context to focus the triage.

## Procedure

1. **Prepare the log set.** Gather EVTX files covering the incident
   window; verify completeness (Security, System, Sysmon/Operational,
   PowerShell) and note gaps that limit rule coverage.
2. **Run the built-in hunt rules.** Execute Chainsaw's hunt mode against
   the log directory for a first-pass triage. Review detections grouped
   by tactic and severity before drilling into specifics.
3. **Apply Sigma rules.** Run your curated Sigma rule set (converted for
   Chainsaw) to test both generic and organization-specific detections
   against the logs — this doubles as detection validation.
4. **Triage systematically.** For each hit, examine the full event
   record (not just the matched fields), establish whether the activity
   is benign (admin tooling, software deployment), suspicious, or
   malicious, and record the disposition with evidence.
5. **Pivot on findings.** Extract IOCs from confirmed hits (process
   paths, command lines, IPs, users) and re-hunt across the full log
   set and other hosts for the same indicators.
6. **Search mode for hypotheses.** Use Chainsaw's search capability for
   hypothesis-driven queries that rules miss — rare strings, specific
   event ID combinations, or time-bounded activity around a known
   incident timestamp.
7. **Export for the timeline.** Export relevant detections in CSV/JSON
   with normalized timestamps and merge into the master incident
   timeline alongside network and EDR evidence.
8. **Feed back into detection engineering.** Promote validated
   Chainsaw/Sigma rules to the SIEM as production detections, and file
   tuning notes for rules that false-positived on your environment.

## Expected outputs

- Hunt and Sigma-scan outputs with triage dispositions per detection.
- Pivot IOCs and cross-host hunt results.
- Timeline-ready event exports merged into the incident timeline.
- New or tuned SIEM detections from validated rules.

## Pitfalls

- Chainsaw is only as good as the logs: missing Sysmon or PowerShell
  channels silently disables large rule categories — check coverage
  first.
- Built-in rules false-positive on legitimate admin activity — maintain
  an allow-list of known-good tooling and behaviors.
- Hunting without a hypothesis on huge log sets produces noise —
  bound hunts by time window and incident context.
- Rule updates matter: stale rules miss new TTPs — update before each
  engagement.
- Treating "no hits" as "clean" — targeted attackers evade generic
  rules; hypothesis-driven searching still applies.

## References

- Chainsaw project documentation (hunt rules, Sigma support)
- Sigma rule specification (SigmaHQ)
- Microsoft Learn: Windows event ID documentation
- MITRE ATT&CK (tactic-grouped triage reference)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
