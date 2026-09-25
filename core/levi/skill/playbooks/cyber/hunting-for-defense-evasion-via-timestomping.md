---
skill_id: cyber_hunting_for_defense_evasion_via_timestomping
name: Hunting for Defense Evasion via Timestomping
description: Detect timestomping anti-forensics by comparing filesystem timestamps against USN journal, MFT, and log evidence.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, forensics, anti-forensics]
version: 1.0.0
---
## Purpose

Timestomping modifies file timestamps (MAC times) to blend malicious files
into legitimate timelines or to backdate implants — a defense-evasion and
anti-forensics technique. This playbook covers detecting timestomped files
by cross-referencing filesystem timestamps with independent time sources:
the USN journal, MFT attributes, event logs, and prefetch.

## When to use

- During forensic analysis when file timelines look suspiciously clean
  or implants appear "old."
- Investigating intrusions where the attacker is known to use
  anti-forensics.
- Validating the integrity of timeline evidence before presenting
  findings.
- Hunting for known timestomping utility execution.

## Prerequisites

- Forensic images or live-collection artifacts: $MFT, USN journal,
  event logs, prefetch, and Shimcache/Amcache.
- Timeline-analysis tooling capable of showing $STANDARD_INFORMATION
  vs. $FILE_NAME timestamp discrepancies.
- Knowledge of normal timestamp behavior for the OS and applications
  in the environment.

## Procedure

1. **Understand the tell.** NTFS stores two timestamp sets per file:
   `$STANDARD_INFORMATION` (modifiable by timestomping tools) and
   `$FILE_NAME` (set at creation, rarely modified by tools). A
   discrepancy — especially creation time *after* modification time, or
   $SI times older than $FN times — is the classic timestomp indicator.
2. **Extract both timestamp sets.** Parse the $MFT and compare $SI vs.
   $FN timestamps for executables, DLLs, and scripts in suspicious
   locations. Flag files where $SI creation predates $FN creation or
   where $SI times are suspiciously round/identical across files.
3. **Cross-reference the USN journal.** The USN journal records file
   operations with its own timestamps independent of file MAC times.
   Look for files whose journal activity (creation, rename, data
   writes) is far newer than their claimed timestamps.
4. **Corroborate with execution artifacts.** Check prefetch (last-run
   times), Shimcache/Amcache (first-execution timestamps), and event
   logs (4688 process creation, Sysmon file-create) — a file claiming
   a 2019 timestamp but first executed last Tuesday is timestomped.
5. **Hunt the timestomping tools.** Search for execution of known
   timestomping utilities and PowerShell/.NET timestamp-manipulation
   code (`LastWriteTime` setters, ntdll `NtSetInformationFile` usage)
   in Script Block Logging and process telemetry.
6. **Assess intent and scope.** Timestomping indicates a conscious
   anti-forensics effort — treat it as an escalation signal. Determine
   which files were stomped and reconstruct their true timeline from
   the corroborating sources.
7. **Rebuild the true timeline.** Produce a corrected timeline using
   $FN times, USN journal, and execution artifacts, clearly marking
   which timestamps are attacker-modified and which are corroborated.
8. **Document for defensibility.** Record the discrepancy evidence
   per file (both timestamp sets, journal excerpts, corroborating
   events) so findings withstand scrutiny.

## Expected outputs

- A list of timestomped files with $SI/$FN discrepancies documented.
- Corroborating evidence per file (USN, prefetch, event logs).
- A corrected incident timeline with modified timestamps flagged.
- Detections for timestomping-utility execution and timestamp
  anomalies.

## Pitfalls

- Legitimate software (installers, updaters) can produce odd
   timestamps — require the $SI/$FN discrepancy pattern, not just
   "old-looking" files.
- Copying files preserves $FN creation semantics in confusing ways —
   understand NTFS timestamp inheritance before concluding malice.
- The USN journal rolls over — on long-dwell intrusions the journal
   may no longer cover the stomping event; note the gap.
- Timestomping detection proves anti-forensics effort, not the
   underlying crime — still build the full attack chain.
- Some backup/restore operations legitimately reset timestamps —
   correlate with backup schedules.

## References

- MITRE ATT&CK: T1070.006 (Timestomp)
- NIST SP 800-86: forensic techniques in incident response
- NTFS timestamp-behavior documentation and forensic references
- $MFT parsing tool documentation (timeline-analysis tools)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
