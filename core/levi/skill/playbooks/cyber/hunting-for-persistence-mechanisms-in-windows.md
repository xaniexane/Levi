---
skill_id: cyber_hunting_for_persistence_mechanisms_in_windows
name: Hunting for Persistence Mechanisms in Windows
description: Comprehensive Windows persistence hunt: registry, services, tasks, WMI, startup folders, and DLL hijacking with baselining discipline.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, windows]
version: 1.0.0
---
## Purpose

Persistence is how intrusions survive reboots and remediation — and
attackers use dozens of Windows mechanisms, from Run keys to WMI
subscriptions to DLL hijacking. This playbook is the comprehensive
persistence-hunting framework: enumerating mechanisms, baselining
legitimate entries, and identifying the anomalous ones across the fleet.

## When to use

- Post-compromise: ensuring all persistence is found before declaring
  remediation complete.
- Proactive threat hunting for stealthy persistence on high-value
  hosts.
- Validating that EDR auto-remediation actually removed persistence
  (it often removes the binary but not the mechanism).
- Building a persistence-monitoring program.

## Prerequisites

- Autoruns-class enumeration capability across the fleet (EDR,
  Velociraptor, or scripted collection) — persistence hunting needs
  the full mechanism inventory, not just one registry key.
- A gold-image or known-good baseline per host role.
- Change-control records (software deployments) to explain legitimate
  new entries.
- Sufficient log retention to date when each persistence entry was
  created.

## Procedure

1. **Enumerate all mechanisms.** Collect the full persistence
   inventory: Run/RunOnce keys, services, scheduled tasks, WMI event
   subscriptions, startup folders, Winlogon entries, AppInit DLLs,
   LSA providers, Office add-ins/templates, browser extensions, and
   accessibility-feature replacements. Partial enumeration misses
   persistence by design.
2. **Baseline per host role.** Build known-good persistence sets from
   gold images and clean reference hosts per role. Legitimate software
   (agents, updaters) creates extensive persistence — the baseline is
   what separates it from attacker additions.
3. **Diff and rank anomalies.** Compare each host's inventory against
   its role baseline. Rank unknowns by: signer status (unsigned is
   higher risk), path (temp, user-writable, unusual), creation time
   (clustered with incident window), and prevalence (rare fleet-wide).
4. **Validate creation context.** For each suspicious entry, determine
   when and how it was created: correlate with process-creation logs,
   installer activity, and the incident timeline. Attacker persistence
   clusters around intrusion timestamps.
5. **Check the payload, not just the pointer.** A Run key pointing to
   a legitimate binary with malicious arguments (or a hijacked DLL
   path) is still persistence — inspect targets, arguments, and DLL
   load paths, not just entry names.
6. **Hunt the exotic mechanisms.** After covering the common ones,
   check: accessibility binaries (sethc/utilman replacement), Netsh
   helper DLLs, print-monitor DLLs, LSASS drivers, COM hijacking,
   and boot/logon scripts. Attackers choose exotic mechanisms
   precisely because hunters skip them.
7. **Remove completely and verify.** Remediation must remove the
   mechanism *and* the payload: delete the persistence entry, remove
   the binary, and re-enumerate to confirm. Reboot and re-check —
   some persistence re-establishes itself from secondary mechanisms.
8. **Operationalize monitoring.** Convert the enumeration into
   recurring collection with alerting on new persistence entries
   outside change windows, and integrate with software-deployment
   records to auto-explain legitimate additions.

## Expected outputs

- Full persistence inventories per host with baseline diffs.
- Investigated anomalies with creation-context evidence and
  dispositions.
- Complete remediation records (mechanism + payload removed,
  verified).
- A recurring persistence-monitoring program with alerting.

## Pitfalls

- Checking only Run keys — modern attackers expect that; enumerate
   everything.
- Removing the binary but leaving the persistence entry (or vice
   versa) — both halves must go, verified by re-enumeration.
- Legitimate software creates enormous persistence volume —
   without baselines and change records, the hunt is unmanageable.
- Persistence timestamps can be timestomped — corroborate creation
   times with logs.
- Declaring remediation complete without a reboot-and-recheck cycle.

## References

- MITRE ATT&CK: persistence tactics TA0003 (technique family)
- Sysinternals Autoruns documentation (mechanism reference)
- NIST SP 800-86: forensic techniques in incident response
- Vendor EDR documentation for persistence-visibility features
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
