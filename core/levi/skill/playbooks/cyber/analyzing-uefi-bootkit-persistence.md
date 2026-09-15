# Analyzing UEFI Bootkit Persistence

See also: analyzing-bootkit-and-rootkit-samples.md

## Purpose

Detect and characterize UEFI-level persistence — malicious DXE drivers, tampered bootloaders, or modified firmware images that survive OS reinstalls. Because a bootkit executes before the operating system, this playbook works from firmware images and pre-OS artifacts rather than live OS telemetry, and ends with a hardware-trust decision: reflash or retire.

UEFI analysis is the deepest persistence investigation most teams will perform. The guiding principle: never trust the compromised system's own view of its firmware — establish ground truth externally.

## When to use

- An incident shows persistence that survives OS reinstallation or disk replacement.
- Firmware integrity monitoring (or a CHIPSEC scan) flags unexpected UEFI modules or modified boot variables.
- Threat intel indicates the actor uses bootkits, and you need to check exposed systems.
- Post-acquisition of a suspicious machine where firmware tampering is in scope.
- Supply-chain verification of new hardware before it enters a sensitive environment.

## Prerequisites

- Written authorization from the asset owner and security leadership to extract and analyze firmware, including approval for any destructive steps (chip-off extraction, flashing). Define which machines are in scope.
- A known-good firmware image for the exact make, model, and BIOS version under test — without a baseline, "different" is not "malicious."
- A hardware toolkit: SPI programmer (for external flash reads when software reads are blocked), a clean analysis workstation, and the vendor's official firmware update utility for recovery.
- Chain of custody: hash every extracted firmware image at acquisition, record the extraction method, tool versions, and handler identity. Firmware images are evidence.
- Assume the suspect machine is hostile: never boot it on a production network; extract firmware with the machine powered off where possible.
- A recovery plan: know how you will restore the machine (vendor image, external programmer) before you start pulling firmware apart.

## Procedure

1. Establish the baseline. Obtain the vendor's official firmware for the exact model and version, verify its signature/hash against the vendor's published values, and record the expected DXE driver list, boot variables, and Secure Boot state.
2. Extract the suspect firmware. Prefer a software read first (CHIPSEC's SPI dump on a powered-off or recovery-booted machine); if software access is locked, use an external SPI programmer with a clip. Hash the image immediately (SHA-256) and log the method.
3. Inventory the firmware volumes. Open the image in UEFITool (or UEFITool NE) and list all firmware volumes, files by GUID, and DXE drivers. Compare against the baseline: new GUIDs, replaced modules, or size anomalies in existing modules are the primary indicators.
4. Inspect suspicious modules statically. Extract any unknown or modified DXE driver and examine its strings, imports, and embedded certificates. Look for: network stack usage in a driver that should not need it, references to disk or NVRAM writes, and hardcoded URLs or IPs. Note which boot phase the driver loads in (DXE drivers run before the OS loader).
5. Check the boot chain configuration. Examine: the EFI System Partition contents (`\EFI\Boot\bootx64.efi`, `\EFI\Microsoft\Boot\bootmgfw.efi` — compare hashes to known-good), the BootOrder/Boot#### NVRAM variables (unexpected entries), Secure Boot state (enabled with your keys, or disabled/tampered), and the Windows BCD for unusual loaders.
6. Run CHIPSEC assessments. Execute relevant CHIPSEC modules (e.g., `chipsec_main -m common.bios_wp` for BIOS write-protection status, `common.secureboot.variables` for Secure Boot variable integrity) and record pass/fail with the CHIPSEC version. Disabled write protection plus an unknown DXE driver is a strong bootkit indicator.
7. Dump and inspect NVRAM variables. Use CHIPSEC's UEFI utilities to list NVRAM variables and compare against the baseline; bootkits sometimes store configuration or second-stage URLs in custom variables. Document any variable not present in the known-good image.
8. Correlate with OS-level signs. If the machine was previously booted: check for the bootkit's OS-stage payload (unexpected early-boot drivers, WMI or scheduled-task persistence that reappears after cleaning, EDR tampering). The firmware component's job is usually to reinstall the OS-stage malware — find both halves.
9. Sweep the fleet for the indicators. Once the bootkit's module GUIDs, hashes, or behavioral signs are characterized, check other machines of the same model/fleet: compare their firmware inventories and Secure Boot states. A bootkit found on one machine of a batch warrants checking the batch.
10. Make the trust decision. If firmware tampering is confirmed: the only reliable remediation is reflashing from a known-good vendor image via an external programmer (in-OS flashing cannot be trusted on a compromised firmware), followed by re-verification. If the flash chip itself is suspect or reflashing fails verification, retire the hardware. Document the decision and rationale.

## Key tools & commands

- CHIPSEC: `chipsec_main -m common.bios_wp`, `chipsec_main -m common.secureboot.variables` for write-protection and Secure Boot checks; `chipsec_util spi dump rom.bin` for firmware extraction where supported; `chipsec_util uefi` subcommands for parsing firmware volumes and listing NVRAM variables.
- UEFITool / UEFITool NE for parsing firmware images into volumes, files, and sections by GUID, and extracting individual modules.
- `flashrom -p <programmer> -r extracted.rom` for external SPI reads; `sha256sum extracted.rom` immediately after.
- `bcdedit /enum all` (Windows, from a clean boot) for boot configuration review; compare ESP file hashes with `Get-FileHash`.
- Vendor firmware update utilities and published hashes for the baseline.

## Expected outputs

- Hashed suspect and baseline firmware images with extraction-method logs.
- A firmware volume/module inventory diff: new, replaced, or anomalous modules with GUIDs.
- Static findings on suspicious DXE drivers (strings, imports, phase, anomalies).
- Boot-chain review: ESP file hashes, NVRAM boot entries, Secure Boot state, BCD anomalies.
- CHIPSEC module results with versions.
- NVRAM variable comparison against baseline.
- OS-stage correlation findings (both halves of the persistence).
- Fleet-sweep results for sibling machines.
- The trust decision: reflash (with post-flash verification) or retire, with rationale.

## Pitfalls

- No baseline: without the exact vendor image, OEM customizations look like tampering. Match model, version, and region.
- Trusting in-OS firmware reads or flashes on a compromised machine — a bootkit can lie to software reads. External SPI extraction is the ground truth.
- Confusing legitimate OEM/AV DXE drivers (some endpoint products install boot-time components) with malware; check the signer and the vendor's documentation.
- Reflashing from inside the compromised OS and declaring victory — verify the reflash with an external read afterward.
- Forgetting the OS stage: cleaning firmware but leaving the OS payload means reinfection on next boot; cleaning the OS but leaving firmware means the same.
- CHIPSEC hardware compatibility: CHIPSEC does not support every chipset — a failed module run is inconclusive, not a clean bill of health. Note the platform support explicitly.
- Bricking risk: external flashing with the wrong image or interrupted writes can brick the board. Verify image compatibility twice and keep the original dump restorable.

## References

- MITRE ATT&CK T1542.003 (Pre-OS Boot: Bootkit) — the technique definition and detection guidance.
- CHIPSEC documentation (GitHub: chipsec/chipsec) — module and `chipsec_util` reference.
- UEFITool documentation — firmware image parsing.
- NIST SP 800-147 "BIOS Protection Guidelines" and SP 800-155 "BIOS Integrity Measurement Guidelines."
- UEFI Specification (uefi.org) — DXE driver model and boot phases.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
