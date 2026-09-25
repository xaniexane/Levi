---
skill_id: cyber_hunting_for_registry_persistence_mechanisms
name: Hunting for Registry Persistence Mechanisms
description: Hunt the full range of registry persistence beyond Run keys: Winlogon, AppInit, LSA providers, COM hijacking, and ASEP locations.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

The Windows registry hosts dozens of auto-start extensibility points
(ASEPs) beyond the familiar Run keys — Winlogon notifications, AppInit
DLLs, LSA authentication packages, COM hijacking, Netsh helpers, and
more. Attackers deliberately choose obscure ASEPs. This playbook covers
systematically hunting registry persistence across the full ASEP set.

## When to use

- Comprehensive persistence sweeps after a compromise.
- Hunting for stealthy persistence that survived a Run-key-only check.
- Building registry-monitoring detections.
- Validating Autoruns-class tool coverage of ASEP locations.

## Prerequisites

- Fleet-wide registry enumeration (EDR, Velociraptor, or scripted
  collection) covering HKLM and per-user hives.
- A comprehensive ASEP list (Autoruns' coverage is the practical
  reference) and gold-image baselines per host role.
- Registry auditing or Sysmon events 12/13/14 for change-dating where
  available.
- Change records for legitimate software installations.

## Procedure

1. **Work from a complete ASEP list.** Enumerate: Run/RunOnce (all
   hives), Winlogon (Shell, Userinit, Notify, GinaDLL), AppInit_DLLs,
   LSA packages/providers, Services (ImagePath), COM InprocServer32
   hijacks, Netsh helpers, print monitors, Office add-ins, browser
   helper objects/extensions, BootExecute, and image-hijack (IFEO)
   debugger entries. Work the list, not memory.
2. **Collect values with metadata.** For each ASEP entry record the
   value data, the target binary's signer/hash, and the key's
   LastWrite time. The target's properties matter more than the entry
   name.
3. **Diff against gold baselines.** Compare per host role. Rank
   unknowns by signer status, path anomaly, and LastWrite clustering
   with incident windows. Rare-fleet-wide entries get priority review.
4. **Inspect hijack-style entries.** COM hijacking and IFEO debugger
   entries redirect legitimate invocations — verify that the
   InprocServer32 DLL or debugger target is the legitimate one, not a
   planted substitute. Check DLL paths for hijackable locations.
5. **Date the changes.** Use key LastWrite times, Sysmon registry
   events, and 4657 audit events to date entry creation; correlate
   with process-creation logs to find the installing process.
6. **Validate the targets.** For each suspicious target binary: check
   signature, hash reputation, and behavior (what does it do when run?).
   A legitimate binary with malicious arguments is still persistence —
   read the full command line.
7. **Remove and verify.** Delete malicious entries, remove payloads,
   and re-enumerate to confirm. Reboot high-value hosts and re-check —
   layered persistence re-establishes cleaned entries.
8. **Monitor the ASEP set.** Deploy registry-integrity monitoring on
   the high-risk ASEP paths with alerting on changes outside change
   windows, integrated with software-deployment records.

## Expected outputs

- ASEP inventories per host with baseline diffs and dispositions.
- Hijack validations (COM, IFEO) with target analysis.
- Removal verification records.
- Registry-monitoring rules for high-risk ASEP paths.

## Pitfalls

- Enumerating only Run keys — the entire point of this playbook is
   the other 90% of ASEPs.
- Trusting entry names: attackers name entries to look legitimate
   ("Windows Update Service") — validate targets, not names.
- LastWrite times update on any value change and can be misleading —
   corroborate with logs.
- Per-user hives require the user context — offline/system-only
   enumeration misses HKCU persistence; collect loaded hives.
- Legitimate security and management tools occupy many ASEPs —
   baseline thoroughly before alerting.

## References

- MITRE ATT&CK: T1547 (Boot or Logon Autostart Execution)
  sub-techniques
- Sysinternals Autoruns documentation (ASEP coverage reference)
- Microsoft Learn: registry structure and ASEP documentation
- NIST SP 800-86: forensic techniques in incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
