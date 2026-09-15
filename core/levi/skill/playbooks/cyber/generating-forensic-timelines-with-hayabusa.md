---
skill_id: cyber_generating_forensic_timelines_with_hayabusa
name: Generating Forensic Timelines with Hayabusa
description: Build high-speed forensic timelines from Windows event logs with Hayabusa for rapid incident triage and investigation.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, windows, timeline]
version: 1.0.0
---
## Purpose

Hayabusa is a fast, Sigma-rule-based Windows event-log analyzer that
turns EVTX files into prioritized timelines — ideal for rapid triage when
you need to know "what happened on this host" quickly. This playbook
covers running Hayabusa against collected event logs, interpreting its
output, and folding results into the investigation timeline.

## When to use

- Initial triage of a suspect Windows host: get a prioritized event
  timeline in minutes.
- Incident response where EVTX files have been collected but full SIEM
  parsing is too slow or unavailable.
- Validating hunting hypotheses against historical host logs.
- Training analysts on Windows event-log investigation.

## Prerequisites

- Collected EVTX files (Security, System, Sysmon, PowerShell channels)
  from the host(s) in scope, with chain-of-custody records.
- A Hayabusa build with current detection rules and geo-IP data if
  needed; run it on an analysis workstation, not the suspect host.
- Baseline knowledge of the host's role so legitimate admin activity
  can be distinguished from attacker activity.
- Timezone awareness: confirm the log timezone before merging with
  other sources.

## Procedure

1. **Prepare the input.** Assemble the EVTX set for the host and confirm
   coverage of the incident window. Note any missing channels (no Sysmon
   means limited process-creation detail — set expectations).
2. **Run a CSV timeline scan.** Execute Hayabusa's timeline generation
   against the EVTX directory. Start with default rules to get the full
   prioritized event list before narrowing.
3. **Triage by severity and tactic.** Work the output top-down: critical
   and high severity detections first, grouped by MITRE ATT&CK tactic.
   Correlate related events (logon → process creation → persistence)
   into candidate attack chains.
4. **Filter to the window and accounts.** Narrow to the compromise window
   and the users/hosts in scope. Exclude known-good admin tooling and
   scheduled maintenance to reduce noise.
5. **Validate key detections.** For each significant hit, go back to the
   raw event (full XML/record) to confirm the detection fired on real
   attacker behavior and not a benign pattern — rule-based triage still
   needs analyst judgment.
6. **Pivot on findings.** Use process names, command lines, IPs, and
   account names from the timeline as pivots: search the fleet for the
   same indicators and pull additional logs (firewall, proxy) for the
   correlated timestamps.
7. **Merge into the master timeline.** Export the relevant events with
   normalized UTC timestamps and merge with network and EDR evidence to
   build the incident's unified timeline.
8. **Update rules from lessons learned.** When the investigation reveals
   attacker behavior Hayabusa missed, write or tune Sigma rules and
   contribute them back to your rule set so the next triage catches it.

## Expected outputs

- A prioritized Hayabusa timeline (CSV) for each host in scope.
- Triaged attack-chain candidates with validation notes.
- Pivot indicators for fleet-wide hunting.
- Merged incident timeline entries with UTC normalization.
- New or tuned Sigma rules from investigation findings.

## Pitfalls

- Hayabusa output is only as good as the logs collected — missing
  channels or overwritten logs create blind spots no tool can fix.
- Rule-based triage produces false positives on admin tooling (PsExec,
   WMI, remote PowerShell) — baseline legitimate admin behavior.
- Timestamps must be normalized before merging with other sources;
   Hayabusa preserves log time, which may not be UTC.
- Running analysis tools on the suspect host contaminates it — always
   analyze copies on a separate workstation.
- Do not treat "no critical detections" as "host is clean" — targeted
   attackers evade generic rules; hypothesis-driven hunting still
   applies.

## References

- Hayabusa project documentation (usage and rule syntax)
- Sigma rule specification (SigmaHQ)
- Microsoft Learn: Windows event ID references
- NIST SP 800-86: forensic techniques in incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
