---
skill_id: cyber_detecting_suspicious_powershell_execution
name: Detecting Suspicious PowerShell Execution
description: Detect malicious PowerShell usage via Script Block Logging and AMSI telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [powershell, windows, detection]
version: 1.0.0
---
## Purpose

PowerShell is the most abused native tool on Windows — fileless execution, encoded commands, and reflective loading all flow through it. This playbook builds PowerShell-specific detection on Script Block Logging (Event ID 4104), module logging, and AMSI telemetry: catching obfuscation, suspicious cmdlets, and living-off-the-land patterns without breaking legitimate automation.

## When to use

- You need PowerShell-focused detection beyond generic LOLBin rules.
- Script Block Logging is enabled but nobody reviews the data.
- Threat hunting for fileless tradecraft.
- Purple-team results show PowerShell bypasses going undetected.

## Prerequisites

- PowerShell Script Block Logging enabled (Event ID 4104) via GPO, Module Logging (4103) optionally, and transcription for high-risk hosts.
- AMSI telemetry or EDR with script-content inspection.
- Centralized collection of 4104/4103 events (high volume — plan license/storage).
- Baseline of legitimate PowerShell automation: admin scripts, SCCM, deployment tools, and their content patterns.

## Procedure

1. Enable and verify deep logging first. Confirm Script Block Logging captures script content (4104 includes de-obfuscated script blocks — this defeats most obfuscation), Module Logging records pipeline execution, and logs reach the SIEM. Test with a benign obfuscated script: if 4104 shows the decoded content, your visibility is working. Attackers' first move is often disabling logging — alert on 4104 stream interruptions per host.
2. Detect obfuscation and evasion. Alert on: -EncodedCommand / -enc usage (especially from unusual parents), heavy string concatenation and character-code obfuscation, AMSI bypass strings and patterns, attempts to disable Script Block Logging or AMSI, and PowerShell launched with -NoProfile -NonInteractive -ExecutionPolicy Bypass in combination. Single flags are weak; stacked evasion flags are strong.
3. Detect suspicious cmdlet and .NET usage. Alert on: Invoke-Mimikatz/Invoke-Shellcode-style function names, Add-Type with P/Invoke to suspicious APIs, WebClient/Invoke-WebRequest downloading + IEX patterns (download cradles), credential-access cmdlets outside admin tooling, and WMI/CIM cmdlets used for lateral movement. Maintain a weighted keyword list tuned to your environment — generic lists need local tuning.
4. Weight parent process and context heavily. PowerShell spawned by winword.exe, excel.exe, browsers, or wscript.exe is the classic malicious pattern; PowerShell spawned by SCCM or admin consoles is usually legitimate. Build rules on (parent, command pattern) pairs and suppress documented automation by script hash or signed-script policy rather than blanket parent exclusions.
5. Hunt fileless and in-memory tradecraft. Query 4104 for: reflective-loading indicators, assembly loading from byte arrays, Empire/Nishang-style module names, and encoded payloads that decode to network endpoints. Correlate with process-creation (Sysmon Event 1) and network telemetry — fileless PowerShell still makes network connections and spawns processes.
6. Respond with credential-awareness. Malicious PowerShell often precedes credential theft: on confirmed malicious execution, isolate the host, assume credentials in memory are compromised, hunt for the delivery vector (phishing document, exploitation), and check for persistence (WMI, scheduled tasks, registry) the script established. Then constrain PowerShell via Constrained Language Mode and application control where business allows.

## Expected outputs

- PowerShell detection rules: obfuscation/evasion, suspicious cmdlets, download cradles, parent-context — tuned against 4104 history.
- Logging-health monitoring: 4104 stream interruption alerts per host.
- Legitimate-automation baseline with suppression method (hash/signing, not blanket exclusion).
- Constrained Language Mode / application-control rollout plan.

## Pitfalls

- 4104 volume is enormous — aggregate and alert on patterns, never raw events.
- Legitimate admin scripts use encoded commands and web requests; tune with local baselines, not internet blocklists.
- Attackers disable Script Block Logging — monitor the logging pipeline itself.
- Constraining PowerShell without testing breaks administration — pilot with audit mode.
- PowerShell 2.0 / downgrade attacks bypass AMSI — monitor for and remove legacy PowerShell versions.

## References

- Microsoft Learn: PowerShell logging (Script Block Logging, Module Logging), AMSI; MITRE ATT&CK T1059.001 (PowerShell) — https://attack.mitre.org/techniques/T1059/001/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
