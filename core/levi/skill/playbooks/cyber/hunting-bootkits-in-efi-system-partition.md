---
skill_id: cyber_hunting_bootkits_in_efi_system_partition
name: Hunting Bootkits in the EFI System Partition
description: Detect bootkit implants by auditing EFI System Partition contents, boot configuration, and Secure Boot state against known-good baselines.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, firmware, forensics]
version: 1.0.0
---
## Purpose

Bootkits persist below the operating system by tampering with UEFI boot
components in the EFI System Partition (ESP) or boot configuration —
surviving OS reinstalls and hiding from most endpoint tools. This playbook
covers hunting for bootkit implants through ESP auditing, boot-loader
integrity checks, and Secure Boot validation.

## When to use

- Suspected firmware-level persistence after OS-level remediation
  failed to remove an infection.
- Threat intel describes bootkit campaigns affecting your hardware or
  sector.
- Acquiring high-value or executive systems where deep persistence must
  be ruled out.
- Building a secure-boot attestation program.

## Prerequisites

- A known-good baseline: hashes of legitimate bootloaders and ESP
  contents for your hardware models and OS builds.
- Ability to mount and hash the ESP offline (from a forensic image or
  trusted recovery media — not from the potentially compromised OS).
- Secure Boot status inventory across the fleet.
- Firmware-update tooling from the hardware vendor for remediation.

## Procedure

1. **Establish the known-good baseline.** From clean reference systems
   (fresh vendor media, matching models), record ESP file listings,
   hashes of bootloaders (`bootmgfw.efi`, `shimx64.efi`, `grubx64.efi`),
   and expected BCD/boot-entry configurations.
2. **Collect the ESP forensically.** Mount the ESP from a forensic image
   or trusted offline media. Do not trust listings from the live,
   potentially compromised OS — a bootkit can filter what the OS sees.
3. **Diff against baseline.** Compare file names, sizes, hashes, and
   timestamps against known-good. Flag unknown EFI binaries, modified
   bootloaders, unexpected boot entries, and recently changed files
   inconsistent with update history.
4. **Inspect boot configuration.** Review BCD entries (Windows) or
   efibootmgr entries (Linux) for rogue boot paths, disabled integrity
   checks (`nointegritychecks`, `testsigning` enabled unexpectedly), and
   recovery-environment tampering.
5. **Verify Secure Boot state.** Check that Secure Boot is enabled and
   enforcing, review the DB/DBX (allowed/forbidden signature databases)
   for tampering, and confirm the platform key (PK) is the vendor's —
   bootkits often require Secure Boot disabled or enroll rogue keys.
6. **Check for firmware-update anomalies.** Review firmware version
   history for downgrades or unsigned updates, which can indicate
   firmware-level tampering beyond the ESP.
7. **Corroborate with OS telemetry.** Cross-reference ESP findings with
   early-boot driver loads, unexpected kernel modules, and EDR alerts
   for boot-configuration changes around the same timestamps.
8. **Remediate at the right layer.** ESP-only tampering: restore from
   known-good media and re-enable Secure Boot. Suspected firmware
   compromise: reflash from vendor-signed images; for high-assurance
   cases, replace the hardware. Then re-baseline.

## Expected outputs

- Known-good ESP/bootloader baselines per hardware model and OS build.
- Per-host ESP diff reports with dispositions for each anomaly.
- Secure Boot and firmware-version inventory with gaps flagged.
- Remediation records (restores, reflashes) and updated baselines.

## Pitfalls

- Trusting the live OS to report on its own boot chain — always verify
  offline.
- Legitimate updates change bootloaders — correlate ESP changes with
  patch/update history before declaring malicious.
- Dual-boot and Linux shim configurations look "unexpected" to
  Windows-only baselines — baseline per OS configuration.
- Secure Boot "enabled" in the OS does not prove enforcement — verify
  at the firmware level.
- Reflashing firmware is disruptive — reserve for confirmed firmware
  compromise, and validate the reflash image's signature.

## References

- MITRE ATT&CK: T1542.003 (Pre-OS Boot: Bootkit), T1542.001 (System
  Firmware)
- NIST SP 800-147: BIOS Protection Guidelines; SP 800-155: BIOS
  integrity measurement
- UEFI Forum specifications (Secure Boot)
- Vendor firmware security guidance for your hardware fleet
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
