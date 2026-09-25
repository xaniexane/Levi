---
skill_id: cyber_hunting_for_registry_run_key_persistence
name: Hunting for Registry Run Key Persistence
description: Focused hunt for Run/RunOnce key persistence: enumeration, baseline diffing, and malicious-entry triage across the fleet.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

Run and RunOnce registry keys remain the most common Windows persistence
mechanism — simple, reliable, and frequently the attacker's first choice.
This focused playbook covers hunting Run-key persistence specifically:
complete enumeration, baseline diffing, and efficient triage of malicious
entries at fleet scale.

## When to use

- Quick persistence triage during incident response (Run keys first,
  then the broader ASEP sweep).
- Recurring hygiene hunts for unauthorized auto-start entries.
- Validating software-deployment hygiene (unauthorized installers often
  leave Run keys).
- Training analysts on persistence triage fundamentals.

## Prerequisites

- Fleet-wide registry collection covering all Run/RunOnce locations:
  HKLM\...\Run, HKLM\...\RunOnce, HKCU equivalents per loaded user
  hive, and the Wow6432Node variants on 64-bit systems.
- Gold-image baselines per host role.
- Target-binary analysis capability (hash, signer, sandbox detonation
  for unknowns).
- Software-deployment change records.

## Procedure

1. **Enumerate completely.** Collect all Run/RunOnce values from HKLM,
   HKCU (every loaded user hive — not just the analyst's), and
   Wow6432Node. Missing a hive is missing persistence.
2. **Parse entries fully.** For each value record: name, data (full
   command line with arguments), target binary hash and signer, and
   key LastWrite time. Arguments are where the malice usually lives.
3. **Diff against baselines.** Compare to the role's gold image and to
   fleet-wide prevalence. Entries unique to one host, unsigned, in
   user-writable paths, or created during the incident window go to
   the top of the queue.
4. **Triage by target analysis.** For each unknown: verify the signer,
   check hash reputation, and inspect arguments for obfuscation,
   URLs, encoded PowerShell, or LOLBin patterns. Run unknown binaries
   in the sandbox if needed.
5. **Date and attribute.** Correlate key LastWrite times with
   installation logs, process-creation telemetry, and the incident
   timeline to find what created each entry — this distinguishes
   attacker persistence from user-installed software.
6. **Check RunOnceEx and friends.** Do not forget adjacent keys:
   RunOnceEx, RunServices, and policy-driven Run keys
   (Explorer\Run) — attackers occasionally use these to dodge
   Run-key-only checks.
7. **Remediate and verify.** Delete malicious values, remove target
   payloads, and re-enumerate to confirm removal. For user-hive
   entries, check all user profiles on shared hosts.
8. **Automate the hygiene hunt.** Schedule recurring Run-key collection
   with automatic baseline diffing and alerting on new entries;
   integrate with change management to auto-explain deployment-driven
   additions.

## Expected outputs

- Fleet Run-key inventory with baseline diffs.
- Triaged entries with target analysis and dispositions.
- Attribution: what created each malicious entry and when.
- Verified remediation records.
- A recurring Run-key hygiene analytic.

## Pitfalls

- Collecting only HKLM or only the current user's HKCU — enumerate
   every hive.
- Judging by value name alone — "OneDrive" or "SecurityHealth" names
   are easily spoofed; validate the target and arguments.
- Forgetting Wow6432Node on 64-bit systems — a separate, often
   unchecked location.
- Deleting the value but leaving the payload (or vice versa).
- User-installed "potentially unwanted" software creates constant
   low-grade noise — define policy for PUA vs. malicious handling.

## References

- MITRE ATT&CK: T1547.001 (Registry Run Keys / Startup Folder)
- Sysinternals Autoruns documentation
- Microsoft Learn: registry Run-key documentation
- NIST SP 800-86: forensic techniques in incident response
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
