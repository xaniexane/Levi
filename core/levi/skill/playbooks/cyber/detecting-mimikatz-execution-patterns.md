---
skill_id: cyber_detecting_mimikatz_execution_patterns
name: Detecting Mimikatz Execution Patterns
description: Detect credential-dumping tool execution patterns associated with Mimikatz-class tooling.
risk: low
permissions: []
requires_confirmation: false
tags: [credential-access, detection, windows]
version: 1.0.0
---
## Purpose

Mimikatz-class credential dumping — extracting passwords, hashes, and Kerberos tickets from LSASS memory — is a near-universal step in Windows intrusions. Attackers rename binaries and recompile to dodge signatures, so this playbook focuses on execution patterns that survive renaming: LSASS access behaviors, characteristic command sequences, and the telemetry that exposes them regardless of filename.

## When to use

- You need credential-dumping detection that survives binary renaming.
- EDR flagged LSASS access and you need a triage procedure.
- Threat hunting after a suspected lateral-movement incident.
- Validating detections against purple-team credential-access exercises.

## Prerequisites

- Sysmon with process-access logging (Event ID 10) tuned to capture LSASS access, or EDR with equivalent memory-access telemetry.
- Command-line logging: Sysmon Event ID 1 and/or PowerShell Script Block Logging (4104).
- Baseline of legitimate LSASS accessors (AV, EDR, backup agents) to exclude.
- LSA Protection / Credential Guard status inventory for hardening context.

## Procedure

1. Monitor LSASS process access, not filenames. Alert on processes opening LSASS with memory-reading access masks (notably 0x1010/0x1410-class grants) from unexpected callers. Build the alert on (SourceImage, GrantedAccess) pairs, then exclude documented legitimate accessors by exact image path and signer — attackers can't easily fake both.
2. Detect the characteristic command vocabulary. Even renamed, operators type the same verbs: sekurlsa, logonpasswords, lsadump, dcsync, kerberos::, token::, privilege::debug. Match these strings in command lines, script blocks (4104), and memory artifacts. Also watch for privilege::debug / SeDebugPrivilege enablement preceding LSASS access — a strong precursor signal.
3. Watch for in-memory and renamed variants. Fileless execution (reflective loading, PowerShell-based ports) never touches disk — pair process-access detection with AMSI/script-block telemetry and memory-scan indicators. For renamed binaries, YARA or hash-independent rules on the distinctive strings and PE characteristics catch recompiles that signature AV misses.
4. Correlate access with outcome. LSASS access followed within minutes by lateral movement (new SMB/RDP sessions), DCSync-like replication traffic (Event 4662 on DCs), or mass authentication anomalies means credentials were harvested and are being used — escalate from detection to incident immediately.
5. Triage with a fixed checklist: identify the source process and its parent chain (how did the tool arrive?), determine which account's context it ran in, check for concurrent persistence, and scope fleet-wide for the same source-image hash or command patterns. Assume any credentials on the host are compromised until proven otherwise.
6. Harden to make dumping harder and noisier: enable LSA Protection (RunAsPPL), deploy Credential Guard/VBS where hardware allows, remove unnecessary local admins and standing privileged access, and ensure EDR tamper protection is on — dumping tools often try to kill defenses first.

## Expected outputs

- LSASS-access detection rules keyed on access mask + caller, with legitimate-accessor exclusions.
- Command-vocabulary detections (command line + script block) for dumping verbs.
- Triage checklist and scoping queries for confirmed dumping events.
- Hardening status: LSA Protection / Credential Guard coverage across the fleet.

## Pitfalls

- Alerting on any LSASS access without exclusions fires on every AV/EDR agent — baseline legitimate accessors first.
- Filename or hash rules alone are trivially defeated by renaming/recompiling — always pair with behavior rules.
- PowerShell-based variants evade process-creation rules; Script Block Logging (4104) is essential coverage.
- Treating a dumping alert as 'blocked, done' misses the point — assume credential compromise and hunt for reuse.
- Disabling the alert because 'admins use it for recovery' without scoping who/where creates a permanent blind spot.

## References

- MITRE ATT&CK T1003.001 (OS Credential Dumping: LSASS Memory) — https://attack.mitre.org/techniques/T1003/001/; Microsoft Learn: LSA Protection and Credential Guard; Sysmon Event ID 10 documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
