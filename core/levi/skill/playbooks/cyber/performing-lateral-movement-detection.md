---
skill_id: cyber_performing_lateral_movement_detection
name: Lateral Movement Detection
description: Detect attacker lateral movement with network and authentication telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, lateral-movement, hunting]
version: 1.0.0
---
# Lateral Movement Detection

## Purpose

Initial access is rarely the objective — attackers move laterally to
reach high-value systems. This playbook builds detection for the common
lateral-movement techniques: remote service execution, WMI, RDP/SSH
hopping, and credential replay, using authentication and network
telemetry defenders already collect.

## When to use

- Building or improving lateral-movement detection coverage.
- Hunting during an active incident for additional compromised hosts.
- Validating that EDR/SIEM rules fire on simulated movement.
- Post-incident review of how far an attacker actually spread.

## Prerequisites

- Centralized authentication logs: Windows Security events (4624/4672/
  4648), SSH logs, VPN logs, and EDR process-creation telemetry.
- Network flow or firewall logs showing host-to-host connections on
  admin ports (445, 135, 3389, 22, 5985/5986).
- A baseline of normal administrative movement: jump hosts, admin
  workstations, and service accounts' usual paths.

## Procedure

1. Baseline legitimate movement: document admin jump hosts, patch-
   management service accounts, and normal RDP/SSH patterns so
   detection targets the abnormal.
2. Alert on first-seen admin-protocol connections: a workstation that
   has never initiated SMB/RDP/WinRM to another host doing so now is
   high-fidelity suspicious.
3. Correlate logon types: network logons (type 3) followed by new
   process creation on the target, especially with explicit credential
   use (4648) or SeDebugPrivilege (4672), indicate interactive
   attacker activity rather than service traffic.
4. Watch the classic tooling: PsExec-style service creation (7045),
   WMI process creation (4688 with wmiprvse parent), PowerShell
   remoting (WinRM 5985), and scheduled-task creation on remote hosts.
5. Track credential artifacts: LSASS access on the source host shortly
   before lateral logons suggests harvested credentials in use.
6. Hunt with graph thinking: from any confirmed compromised host,
   enumerate all outbound admin-protocol connections in the following
   hours and triage each destination.
7. Validate with purple-teaming: run controlled lateral-movement
   simulations and confirm each technique fires the expected alert —
   tune until coverage is real, not assumed.
8. Contain by credential: on confirmed movement, force password resets
   for affected accounts, revoke sessions, and isolate hosts before
   rebuilding the timeline.

## Expected outputs

- Detection rules for the core lateral-movement techniques with
  tuning notes.
- A validated coverage matrix from purple-team testing.
- Hunt queries for incident-time scoping.
- Containment actions tied to credential and host isolation.

## Pitfalls

- No baseline: without knowing normal admin movement, every rule is
   either noisy or blind.
- Relying on a single log source: attackers clear or avoid individual
   sensors — correlate authentication, process, and network data.
- Alerting on the tool instead of the behavior: renamed binaries
   evade name-based rules; parent-child and protocol patterns survive.
- Forgetting Linux and cloud: lateral movement is not a Windows-only
   problem — cover SSH and cloud console/API paths too.

## References

- MITRE ATT&CK: Lateral Movement tactic (T1021, T1047, T1570)
- NIST SP 800-92, Guide to Computer Security Log Management
- SANS guidance on lateral-movement hunting
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
