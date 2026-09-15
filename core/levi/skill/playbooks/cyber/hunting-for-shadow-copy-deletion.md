---
skill_id: cyber_hunting_for_shadow_copy_deletion
name: Hunting for Shadow Copy Deletion
description: Detect ransomware-style shadow-copy deletion (vssadmin, wmic, PowerShell) and protect backup/recovery capability.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, ransomware, windows]
version: 1.0.0
---
## Purpose

Deleting volume shadow copies (`vssadmin delete shadows`, `wmic
shadowcopy delete`, PowerShell equivalents) is a hallmark ransomware
preparation step — it destroys local recovery options before encryption.
Detecting it early can mean the difference between recovery and ransom.
This playbook covers detecting shadow-copy deletion, responding to it as
a ransomware precursor, and protecting recovery capability.

## When to use

- Any ransomware investigation: shadow-copy deletion timing reveals
  the attack timeline.
- As a high-priority detection use case: deletion events should page,
  not just log.
- Proactive hunting for ransomware precursors on the fleet.
- Validating backup and recovery resilience.

## Prerequisites

- Process-creation telemetry with command lines (Sysmon/EDR) —
  deletion is invoked via command line, so this is the primary source.
- Security event logs (4688) and PowerShell Script Block Logging for
  scripted variants.
- An inventory of legitimate backup/maintenance tools that manage
  shadow copies (to baseline).
- Tested, offline/air-gapped backups — detection is only half the
  battle.

## Procedure

1. **Know the deletion commands.** The canonical patterns: `vssadmin
   delete shadows /all /quiet`, `wmic shadowcopy delete`, PowerShell
   `Get-WmiObject Win32_ShadowCopy | Remove-WmiObject`, `vssadmin
   resize shadowstorage` (shrinking to zero), bcdedit recovery
   disabling, and wbadmin catalog deletion. Hunt all variants.
2. **Deploy high-priority detections.** Alert immediately on any of
   these invocations outside approved backup tooling — this is a
   page-worthy event, not a next-day review. Include case variations
   and obfuscated forms (PowerShell encoding, WMI method invocation).
3. **Correlate with ransomware precursors.** Shadow-copy deletion
   rarely happens alone: check for concurrent defense impairment
   (Defender/EDR tampering), backup-service stops, GPO changes, and
   mass file-rename or encryption activity in the minutes after.
4. **Identify the actor context.** Determine which process and user
   performed the deletion: ransomware operator, a compromised admin
   account, or (rarely) legitimate maintenance. The parent chain
   distinguishes automated ransomware from manual operator activity.
5. **Respond as an active ransomware event.** Treat confirmed malicious
   deletion as an in-progress ransomware incident: isolate the host(s)
   immediately, hunt fleet-wide for the same indicators, and activate
   the ransomware IR playbook — encryption often follows within
   minutes to hours.
6. **Assess recovery capability.** Verify what recovery options remain:
   offline backups, cloud backups, and surviving shadow copies on
   unaffected hosts. Do not assume backups are intact — ransomware
   operators target backup infrastructure too.
7. **Hunt historically.** Search for prior deletion events across
   retention — earlier deletions may indicate earlier intrusion stages
   or failed ransomware attempts worth investigating.
8. **Harden recovery.** Move backups offline/air-gapped with immutable
   retention, restrict who can manage shadow storage, monitor backup-
   infrastructure access, and rehearse restores — untested backups are
   not backups.

## Expected outputs

- Deletion-event findings with full process context and timelines.
- Ransomware-precursor correlation and IR activation records.
- Recovery-capability assessment (backups verified intact).
- Page-level detections for all deletion variants.
- Backup-hardening improvements with restore-test results.

## Pitfalls

- Treating deletion alerts as low priority — by the time you review
   tomorrow, encryption may be complete; page on these.
- Legitimate backup tools manage shadow copies — baseline them
   precisely to avoid paging on maintenance.
- Focusing only on vssadmin — scripted WMI/PowerShell variants are
   increasingly common; hunt all of them.
- Assuming surviving shadow copies are trustworthy — verify integrity
   before relying on them for recovery.
- Forgetting backup infrastructure: operators delete or encrypt
   backups first — monitor and isolate backup systems.

## References

- MITRE ATT&CK: T1490 (Inhibit System Recovery)
- CISA: ransomware guidance and #StopRansomware advisories
- Microsoft Learn: vssadmin and shadow-copy documentation
- NIST SP 800-34: Contingency Planning Guide
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
