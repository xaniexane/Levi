---
skill_id: cyber_configuring_windows_defender_advanced_settings
name: Configuring Windows Defender Advanced Settings
description: Harden Microsoft Defender Antivirus with ASR rules, cloud protection, network protection, and tamper-proofing.
risk: low
permissions: []
requires_confirmation: false
tags: [endpoint, windows, hardening]
version: 1.0.0
---
## Purpose

Push Microsoft Defender Antivirus from its out-of-box defaults to a hardened, audit-ready state: aggressive cloud-delivered protection, attack-surface-reduction rules, network protection, and tamper protection — with the logging to prove it's working.

## When to use

- Hardening the Windows fleet where Defender is the primary AV/EDR layer.
- Preparing endpoints for compliance audits (CIS benchmarks, internal baselines).
- Reducing malware and ransomware dwell time via cloud-delivered protection and behavioral blocking.
- Standardizing Defender settings via Group Policy or Intune before a fleet rollout.

## Prerequisites

- Admin rights on the endpoints or the management plane (Group Policy, Intune, or SCCM/ConfigMgr).
- A pilot group of representative machines for staged rollout — ASR rules can break line-of-business apps.
- Centralized log collection for Defender operational logs (Event IDs 1006–1121 and ASR rule events).
- Inventory of business-critical applications to test against aggressive blocking rules.

## Procedure

1. **Enable cloud-delivered protection and set it to high.** Turn on cloud-delivered protection and automatic sample submission, and set the cloud protection level to High with an extended timeout (up to 60 seconds). This is the single biggest detection upgrade over defaults — most new malware is classified in the cloud, not by local signatures.
2. **Enable tamper protection everywhere.** Turn on tamper protection (Intune or the Security portal) so local admins, malware, and scripts cannot disable Defender, change exclusions, or remove protection. Verify with a test attempt on a pilot machine — if a "stop service" command succeeds, tamper protection isn't on.
3. **Deploy Attack Surface Reduction rules in audit-then-block.** Roll out ASR rules (block Office child processes, block credential stealing from LSASS, block process injection, block executable content from email/webmail) in **audit mode** first. Review the audit-mode events (Event ID 1121/1122) against the pilot fleet for two weeks, create narrow exclusions for legitimate LOB apps, then switch to block.
4. **Enable network protection and controlled folder access.** Turn on network protection in block mode to stop outbound connections to malicious hosts at the network layer. Enable controlled folder access in audit mode for user document folders — this is the ransomware tripwire — and whitelist legitimate writers before enforcing block mode.
5. **Configure behavior monitoring and PUA protection.** Ensure behavior monitoring and real-time protection are on (they're the fileless-malware backstop), and enable PUA (potentially unwanted application) blocking to cut down adware/bundlers that become initial access vectors.
6. **Harden exclusions — they're the attacker's favorite.** Audit existing exclusions ruthlessly: remove folder-level exclusions that cover too much, never exclude entire drives or system roots, and require change-control approval plus expiry dates for every exclusion. Attackers routinely check Defender exclusions early in an intrusion.
7. **Centralize and alert on Defender telemetry.** Collect Microsoft-Windows-Windows Defender/Operational events into the SIEM. Alert on: threat detections (1006, 1116), real-time protection disabled (5001), ASR blocks (1121), tamper attempts (5007 settings changes), and malware that required a reboot to remove (1009).
8. **Validate with safe simulations.** Run controlled tests: EICAR for signature path, a benign simulated-attack script for behavioral blocking, and an ASR test that mimics Office spawning a child process. Confirm each layer fires and each event lands in the SIEM before declaring the baseline done.

## Expected outputs

- Defender fleet policy: cloud protection High, tamper protection on, ASR rules in block mode with documented exclusions.
- Network protection and controlled folder access enforcing, with audit history for each.
- SIEM alerts on detections, tamper attempts, and protection-state changes; validated with EICAR/behavioral tests.

## Pitfalls

- Flipping ASR rules straight to block without audit mode — guaranteed help-desk tickets and rollbacks.
- Blanket exclusions ("exclude C:\AppData") that neutralize protection on the exact paths malware uses.
- Disabling cloud protection "for privacy" without an equivalent — you lose the newest detections silently.
- Assuming tamper protection is on because the toggle exists in the portal — verify on an endpoint.
- Forgetting that PUA blocking needs user communication, or every bundled-toolbar cleanup becomes a surprise.

## References

- Microsoft Learn — Microsoft Defender Antivirus configuration and ASR rule reference
- CIS Benchmark for Windows 10/11 and Windows Server — Defender settings
- MITRE ATT&CK T1562.001 (Impair Defenses: Disable or Modify Tools) — tamper-evasion context
- NIST SP 800-53 SI-7 / SI-8 (software integrity, malicious code protection)
