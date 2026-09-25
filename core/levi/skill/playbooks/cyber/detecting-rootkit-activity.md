---
skill_id: cyber_detecting_rootkit_activity
name: Detecting Rootkit Activity
description: Detect kernel and boot-level rootkits via memory forensics and integrity checking.
risk: moderate
permissions: []
requires_confirmation: true
tags: [rootkit, memory-forensics, detection]
version: 1.0.0
---
## Purpose

Rootkits subvert the operating system itself, hiding processes, files, and network connections from normal tools — which means live-system analysis can't be trusted. This playbook covers detecting rootkit activity through memory forensics, offline analysis, and integrity cross-checks. Note: confirming a rootkit typically requires acquiring memory or disk images from live production systems, hence the elevated risk and confirmation requirement.

## When to use

- EDR/AV behaves anomalously or is disabled without explanation.
- System exhibits hidden processes, unexplained network connections, or log gaps.
- Threat intel indicates rootkit-capable malware targeting your platform.
- Post-incident verification that a 'cleaned' host is truly clean.

## Prerequisites

- Authorization to acquire memory/disk images from production hosts (this is the confirmation-gated step).
- Memory-forensics tooling (Volatility) and offline analysis capability (Autopsy/Sleuth Kit) in an isolated lab.
- Known-good baselines: clean kernel module/driver lists, boot configuration, and system-file hashes per build.
- Offline boot media for trusted acquisition when the live OS can't be trusted.

## Procedure

1. Treat the live system as untrustworthy from the start. A rootkit can lie to every on-box tool — task managers, AV scanners, even forensic agents. Plan your detection around out-of-band evidence: memory images analyzed offline, disk images examined from a clean system, and network telemetry the rootkit can't alter. Never declare 'clean' based on live-system scans alone.
2. Acquire memory for offline analysis (confirmation-gated). With authorization, capture full memory from the suspect host using a trusted acquisition tool, ideally from a cold-boot or offline state if the rootkit resists. Preserve chain of custody. Analyze offline with Volatility: look for hidden processes (psxview discrepancies), hooked SSDT/IRP tables, malicious kernel drivers, injected kernel code, and network connections with no owning process.
3. Cross-view detection: compare independent views. Enumerate processes, drivers, and files from two independent methods (e.g., live API vs. raw memory structures; OS file listing vs. raw disk parsing) — discrepancies are the classic rootkit indicator. Automate cross-view checks where possible; manual spot-checks don't scale.
4. Check boot integrity. Inspect: Secure Boot status and boot-loader hashes, kernel driver signing enforcement, unexpected boot-start drivers/services, and firmware/BIOS anomalies. Bootkits persist below the OS — if boot integrity is compromised, OS-level remediation is meaningless and the response escalates to firmware recovery.
5. Scope for the rootkit's purpose. Rootkits are concealment, not objectives: determine what was hidden — credential theft, data staging, C2, lateral movement — using network logs and memory artifacts. Hunt fleet-wide for the same driver hashes, infection vectors, and C2 indicators; rootkits are rarely deployed on a single host in targeted intrusions.
6. Remediate at the right layer. User-mode rootkits: reimage from known-good media after evidence preservation. Kernel/bootkits: reimage plus firmware verification/reflash per vendor guidance; if firmware compromise is confirmed, follow hardware-vendor recovery procedures. Reset credentials for accounts active on compromised hosts. Never 'clean' a rootkit in place and return the host to service.

## Expected outputs

- Memory/disk acquisition records with chain of custody (confirmation-gated).
- Offline analysis findings: hidden objects, hooks, malicious drivers, boot anomalies.
- Cross-view discrepancy reports and fleet-hunt results.
- Remediation records: reimage/reflash actions, credential resets, firmware verification.

## Pitfalls

- Live-system tools lie under a rootkit — 'clean scan' from the infected OS means nothing.
- Acquiring memory from production without authorization disrupts users and risks evidence challenges — get approval first.
- Kernel crash dumps and hibernation files are partial substitutes, not replacements, for full memory capture.
- Reimaging without addressing the infection vector and firmware state invites reinfection.
- Attributing every system anomaly to rootkits wastes effort — confirm with memory forensics before escalating.

## References

- Volatility documentation (volatilityfoundation.org); NIST SP 800-86 (integrating forensic techniques); MITRE ATT&CK T1014 (Rootkit) — https://attack.mitre.org/techniques/T1014/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
