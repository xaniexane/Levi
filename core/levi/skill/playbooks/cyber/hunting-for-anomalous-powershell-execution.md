---
skill_id: cyber_hunting_for_anomalous_powershell_execution
name: Hunting for Anomalous PowerShell Execution
description: Detect malicious PowerShell usage via Script Block Logging, AMSI telemetry, and command-line anomaly hunting in endpoint logs.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, windows, powershell]
version: 1.0.0
---
## Purpose

PowerShell is the most abused living-off-the-land tool on Windows:
fileless payloads, encoded commands, and reflective loading all flow
through it. This playbook covers detecting malicious PowerShell via
Script Block Logging (4104), module logging, AMSI events, and
command-line telemetry — plus baselining legitimate administrative use
so hunts do not drown in noise.

## When to use

- Any Windows intrusion investigation: PowerShell is a near-universal
  attacker tool.
- Tuning detections after enabling Script Block Logging or AMSI
  telemetry.
- Hunting for fileless malware and post-exploitation frameworks.
- Validating that PowerShell Constrained Language Mode or WDAC policies
  are effective.

## Prerequisites

- Script Block Logging (event 4104), Module Logging, and PowerShell
  Operational logs collected centrally; AMSI telemetry from Defender/
  EDR where available.
- Process-creation telemetry with command lines (Sysmon event 1 or 4688
  with command-line auditing).
- A baseline of legitimate PowerShell usage: admin scripts, automation
  service accounts, and software-deployment tooling.
- Authority to run hunting queries across endpoint logs.

## Procedure

1. **Verify logging coverage.** Confirm Script Block Logging is enabled
   via GPO on the fleet and events are reaching the SIEM. Gaps here are
   the top reason PowerShell hunts fail — fix collection before
   hunting.
2. **Hunt encoded and obfuscated invocation.** Query process-creation
   logs for `powershell.exe`/`pwsh.exe` with `-EncodedCommand`,
   `-enc`, unusually long command lines, or Base64-shaped arguments.
   Decode and inspect the payloads — legitimate automation rarely needs
   heavy obfuscation.
3. **Hunt Script Block Logging anomalies.** Search 4104 events for
   suspicious keywords and patterns: `Invoke-Mimikatz`-style function
   names, `Net.WebClient`/`DownloadString`, `IEX`, reflection
   (`System.Reflection.Assembly`), AMSI-bypass strings
   (`amsiInitFailed`), and credential-access cmdlets outside admin
   contexts.
4. **Review AMSI detections.** Triage Defender/EDR AMSI alerts on
   PowerShell content — these are high-fidelity because AMSI sees the
   deobfuscated script. Correlate each with the parent process and user.
5. **Baseline and exclude legitimate use.** Build allow-lists for known
   admin scripts (by hash, path, and signing identity) and automation
   accounts. Prefer signed scripts and Constrained Language Mode to
   shrink the legitimate-PowerShell surface that must be baselined.
6. **Correlate with the attack chain.** For each suspicious execution,
   pull the parent process, grandparent chain, network connections made
   by the PowerShell process, and subsequent persistence or lateral-
   movement events to scope the intrusion.
7. **Hunt historically.** Attackers often "live" in PowerShell for weeks —
   run the same queries back across maximum retention to find earlier
   stages of the intrusion.
8. **Convert to detections.** Promote validated patterns to SIEM rules
   (encoded invocation, AMSI bypass attempts, download cradles from
   unusual parents), and push for Constrained Language Mode / WDAC
   enforcement to structurally reduce PowerShell abuse.

## Expected outputs

- Logging-coverage assessment for PowerShell telemetry.
- Hunt findings: suspicious executions with decoded payloads and
  dispositions.
- Correlated attack chains and scoping notes per finding.
- Production SIEM detections with false-positive tuning.
- Hardening recommendations (CLM, WDAC, script signing).

## Pitfalls

- Without Script Block Logging you are blind to script content —
   command lines alone miss fileless and interactive abuse.
- Heavy false positives from admin automation — invest in baselining
   before writing alerting rules.
- AMSI can be bypassed or unloaded — treat AMSI alerts as valuable but
   not as a guarantee of visibility.
- PowerShell 2.0 (downgrade attacks) bypasses modern logging — disable
   v2 via features and alert on its invocation.
- Decoding Base64 payloads may reveal credentials — handle decoded
   content as sensitive.

## References

- Microsoft Learn: "PowerShell logging" (Script Block Logging,
  Module Logging)
- MITRE ATT&CK: T1059.001 (PowerShell), T1562.001 (Impair Defenses:
  AMSI bypass)
- NIST SP 800-92: Guide to Computer Security Log Management
- Defender/AMSI vendor documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
