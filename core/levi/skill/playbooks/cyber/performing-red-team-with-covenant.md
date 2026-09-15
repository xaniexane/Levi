---
skill_id: cyber_performing_red_team_with_covenant
name: Detecting C2 Frameworks Like Covenant
description: Understand Covenant-style C2 tradecraft to detect command-and-control implants and validate defenses through authorized emulation.
risk: low
permissions: []
requires_confirmation: false
tags: [c2, detection, red-team]
version: 1.0.0
---

## Purpose
- This playbook is defensive: it focuses on detecting .NET-based C2 implants and hardening against them, plus authorized emulation strictly for detection validation.
- Teach defenders what Covenant-style C2 looks like on the wire and on the endpoint.
- Build detections for C2 beaconing, staging, and tasking patterns.
- Validate those detections through tightly scoped, authorized emulation.

## When to use
- When threat intelligence links relevant actors to .NET C2 frameworks.
- When building or tuning C2 detections in the SIEM, NDR, or EDR.
- During authorized adversary emulation where C2 simulation is in scope.
- After incidents involving suspected C2, to hunt for similar implant behavior.

## Prerequisites
- Written authorization for any active emulation, with defined targets and time windows.
- An isolated lab for studying C2 tradecraft safely.
- Network and endpoint telemetry: proxy logs, DNS logs, EDR process data, and ideally full packet capture.
- Baseline knowledge of normal encrypted outbound traffic for the environment.

## Procedure
1. Study the C2 framework's tradecraft in a lab: beacon intervals, jitter, URI patterns, encryption, and staging mechanisms.
2. Document network indicators: default ports, certificate characteristics, JA3 fingerprints, and DNS patterns.
3. Document endpoint indicators: process injection targets, persistence mechanisms, and named pipes or other IPC.
4. Build SIEM and NDR detections for the beaconing patterns, starting with the most distinctive features.
5. Hunt historical telemetry for the documented indicators before assuming the environment is clean.
6. If authorized, run tightly scoped emulation against test systems to validate that detections fire.
7. Tune detections based on emulation results, balancing true positives against beacon-like legitimate traffic.
8. Harden the pathways C2 abuses: egress filtering, application allowlisting, and PowerShell or .NET execution controls.
9. Document the full indicator set and detection logic for the SOC runbook.
10. Reassess periodically, since C2 operators customize profiles to evade exactly these detections.

## Expected outputs
- A C2 tradecraft profile with network and endpoint indicators.
- Validated detections for C2 beaconing and staging.
- Hardening recommendations for the abused execution and egress pathways.
- A detection runbook entry for C2 beaconing with investigation steps.
- Hunting queries saved for periodic re-execution against new telemetry.

## Pitfalls
- Running C2 infrastructure without airtight authorization; even emulated C2 looks exactly like real attacks to defenders.
- Building detections on default framework profiles only; operators customize them routinely.
- Alerting on beacon-like patterns without baselining legitimate software updaters and sync agents.
- Studying only default C2 profiles; real operators customize everything.

## References
- MITRE ATT&CK software pages for C2 frameworks, https://attack.mitre.org/software/
- MITRE ATT&CK command and control tactics, https://attack.mitre.org/tactics/TA0011/
- Covenant project documentation for understanding .NET C2 tradecraft
- NSA and CISA guidance on detecting C2
- SANS FOR578 cyber threat intelligence resources on C2 analysis
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
