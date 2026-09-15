---
skill_id: cyber_detecting_t1003_credential_dumping_with_edr
name: Detecting T1003 Credential Dumping with EDR
description: Build EDR detections for ATT&CK T1003 OS credential dumping techniques.
risk: low
permissions: []
requires_confirmation: false
tags: [edr, credential-access, mitre-attack]
version: 1.0.0
---
## Purpose

This playbook maps ATT&CK T1003 (OS Credential Dumping) sub-techniques to concrete EDR detections: LSASS memory, SAM/SYSTEM hive access, NTDS.DIT theft, DCSync, and credential-manager stores. It is the practitioner companion to the ATT&CK page — turning technique descriptions into tuned, low-noise EDR rules.

## When to use

- You need ATT&CK-mapped credential-dumping coverage in your EDR.
- EDR credential-access alerts need tuning or validation.
- Purple-team exercise testing T1003 variants.
- Building a detection-engineering backlog mapped to ATT&CK.

## Prerequisites

- EDR with process, memory-access, file, registry, and network telemetry (or Sysmon equivalent).
- ATT&CK T1003 sub-technique list (T1003.001–T1003.008) as the coverage framework.
- Baseline of legitimate credential-store accessors (backup, AV, EDR, password managers).
- Test environment for safe detection validation.

## Procedure

1. Map each sub-technique to telemetry. T1003.001 LSASS memory → process-access/m memory-read events on lsass.exe. T1003.002 Security Account Manager (reg save HKLM\SAM/SYSTEM) → registry/file-access events. T1003.003 NTDS.DIT (ntdsutil, vssadmin shadow copies on DCs) → process + volume-shadow events. T1003.004 LSA secrets → registry access to HKLM\SECURITY. T1003.006 DCSync → 4662 replication events on DCs. T1003.007 /etc/passwd-shadow → Linux file-access. T1003.008 /etc/security/opasswd and keychains → platform-specific stores. Document the telemetry per sub-technique before writing rules.
2. Write behavior-based rules per sub-technique. For each: define the malicious behavior (not the tool name), the telemetry fields, and the legitimate-use exclusions. Example pattern: alert on non-backup processes reading NTDS.DIT or creating volume shadow copies on DCs; alert on reg.exe saving SAM/SYSTEM hives; alert on unexpected processes accessing /etc/shadow. One rule per sub-technique keeps tuning independent.
3. Baseline legitimate accessors precisely. Backup software, EDR agents, and password-management tools touch credential stores legitimately — exclude by exact image path + signer + parent context, never by sub-technique. Review exclusions quarterly; attackers love hiding behind excluded processes.
4. Correlate dumping with the kill chain. A T1003 alert should automatically pivot to: how the dumping process arrived (parent chain, initial access), whether credentials were used (subsequent PtH/PtT/DCSync), and lateral movement from the host. Build EDR correlation or SIEM rules linking T1003 → T1550/T1558 → TA0008 into single incidents.
5. Validate with purple-team testing. Execute each T1003 variant safely in a lab (or via approved adversary emulation) and confirm the corresponding rule fires with correct severity and context. Untested rules are assumptions — schedule validation per sub-technique and record results in the coverage matrix.
6. Drive the mitigations that reduce T1003 value: Credential Guard/LSA Protection, tiered administration, gMSAs, short-lived cloud credentials, and Linux shadow-file protections. Detection catches dumping; architecture makes dumped material worthless.

## Expected outputs

- T1003 coverage matrix: sub-technique → telemetry → rule → validation status.
- Per-sub-technique EDR rules with documented exclusions.
- Kill-chain correlation: T1003 → credential-use → lateral movement.
- Purple-team validation records per variant.

## Pitfalls

- Tool-name rules (mimikatz.exe) are trivially bypassed — always behavior-based.
- Excluding by sub-technique ('ignore all LSASS access') instead of by legitimate source destroys coverage.
- DCSync detection needs DC-side 4662 logging — endpoint-only EDR misses it.
- Linux/macOS credential stores need separate rules — T1003 isn't Windows-only.
- Untested detections are assumptions — validate each variant, don't assume.

## References

- MITRE ATT&CK T1003 (OS Credential Dumping) and sub-techniques — https://attack.mitre.org/techniques/T1003/; EDR vendor documentation for process/memory telemetry; Microsoft Learn: Credential Guard, LSA Protection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
