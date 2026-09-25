---
skill_id: cyber_detecting_secure_boot_bypass
name: Detecting Secure Boot Bypass
description: Detect attempts to bypass or subvert UEFI Secure Boot.
risk: low
permissions: []
requires_confirmation: false
tags: [secure-boot, firmware, detection]
version: 1.0.0
---
## Purpose

Secure Boot is the anchor of the boot trust chain — bypassing it enables bootkits that survive OS reinstallation. This playbook helps defenders detect Secure Boot bypass attempts and misconfigurations: unexpected bootloader changes, revoked-binary execution, and policy tampering, using firmware and OS telemetry.

## When to use

- You need boot-integrity monitoring as part of a firmware-security program.
- Threat intel describes bootkit activity and you need detection coverage.
- A host shows boot anomalies (unexpected recovery, bootloader changes).
- Auditing Secure Boot posture across the fleet.

## Prerequisites

- Fleet inventory of Secure Boot status (enabled/disabled), UEFI firmware versions, and bootloader hashes per build.
- Windows: Event logs for Code Integrity / Secure Boot (Microsoft-Windows-CodeIntegrity/Operational); Linux: mokutil/sbctl status and kernel logs.
- TPM/measured-boot attestation capability where available (for high-assurance hosts).
- Baseline of authorized bootloaders and their signatures per OS build.

## Procedure

1. Establish the Secure Boot posture baseline. Inventory every host: Secure Boot on/off, platform key (PK) state, forbidden-signature database (dbx) currency, and firmware version. Hosts with Secure Boot disabled or in Setup Mode are your highest-risk population — attackers target them first because bypass is unnecessary.
2. Monitor bootloader and boot-configuration integrity. Alert on: bootloader files (shim, grub, winload) modified outside patching windows, BCD/boot entries changed unexpectedly, new EFI executables appearing in the ESP (EFI System Partition), and dbx/PK modifications. Compare against per-build known-good hashes — bootloaders change rarely, so deviations are significant.
3. Detect bypass-tooling indicators. Alert on: execution of known Secure Boot bypass utilities, tools that manipulate UEFI variables from the OS (bypassing protections), disabling of driver-signature enforcement (DSE) via exploits, and exploitation of revoked-but-still-exploitable bootloaders (the 'revoked binary' problem — old signed bootloaders with known vulnerabilities). Keep the dbx current: Microsoft's revocation updates are the mitigation for this class.
4. Correlate with persistence below the OS. Secure Boot bypass is usually a means to install a bootkit: follow bypass indicators with checks for new boot-start drivers, unexpected kernel modules, and firmware-write attempts. A bypass with no follow-on persistence may be a failed attempt — still investigate, as the attacker learned your posture.
5. Validate with measured boot where it matters. For high-value hosts, use TPM-based attestation to verify the boot chain cryptographically rather than trusting OS-reported status — OS-reported 'Secure Boot: on' can be lied about by sufficiently privileged malware. Discrepancies between attestation and OS reports are critical findings.
6. Remediate decisively: re-enable Secure Boot and restore platform keys where tampered, update dbx and firmware, reimage hosts with confirmed bypass from known-good media, and for suspected firmware persistence follow vendor firmware-recovery procedures. Track bypass attempts as firmware-security incidents, not malware incidents.

## Expected outputs

- Secure Boot posture inventory: status, PK/dbx state, firmware versions per host.
- Boot-integrity detections: bootloader changes, ESP anomalies, dbx/PK tampering, bypass tooling.
- Measured-boot attestation for high-value hosts with discrepancy alerting.
- Firmware-incident response procedure: reimage, key restoration, vendor recovery.

## Pitfalls

- OS-reported Secure Boot status can be falsified by privileged malware — use attestation for high assurance.
- Revoked-but-signed bootloaders remain exploitable until dbx is updated — patching the OS isn't enough.
- Legitimate dual-boot and recovery tools modify boot configuration — baseline per build.
- Disabling Secure Boot 'temporarily' for troubleshooting and forgetting to re-enable is a common finding — audit regularly.
- Firmware updates themselves change boot measurements — coordinate update windows with attestation baselines.

## References

- Microsoft Learn: Secure Boot, dbx updates, and TPM attestation; NIST SP 800-147 (BIOS protection) and SP 800-193 (platform firmware resiliency); MITRE ATT&CK T1542.003 (Pre-OS Boot: Bootkit) — https://attack.mitre.org/techniques/T1542/003/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
