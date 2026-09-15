# Analyzing Bootkit and Rootkit Samples

## Purpose

Safely analyze bootkit and rootkit samples — malware that subverts the boot
process or the operating-system kernel — to determine persistence mechanism,
stealth technique, capabilities, and indicators. Static analysis first;
isolated dynamic analysis only when justified. These are the hardest malware
classes to observe from inside the OS, so methodology discipline matters
more than tooling.

## When to use

- EDR flags a driver, boot-sector modification, EFI variable change, or
  kernel-memory anomaly.
- A disk image contains an unrecognized bootloader, EFI binary, or kernel
  driver tied to an incident.
- Threat intel provides a bootkit/rootkit sample for capability assessment.
- You need IOCs and detection logic for a boot-process or kernel-level
  threat.
- A host exhibits "impossible" behavior (processes invisible to Task
  Manager but visible in memory forensics).

See also: analyzing-uefi-bootkit-persistence.md, analyzing-linux-kernel-rootkits.md

## Prerequisites

- Written authorization from the asset/data owner to analyze the sample
  and, if needed, detonate it in a lab.
- Chain-of-custody notes: hashes of every sample and image, source,
  collection time, lab network configuration, and snapshot states.
- An isolated lab: analysis VM with host-only or no networking, snapshots
  taken before any execution, no production credentials anywhere in the lab,
  no shared folders/clipboard with the host.
- Tooling: disassembler (Ghidra/IDA Free), UEFI image inspection tools,
  Volatility, a kernel-debugger setup if doing dynamic work, and reference
  clean images of the same OS/firmware version for diffing.
- Patience: kernel-level analysis is slow. Budget accordingly and don't
  shortcut to conclusions.

## Procedure

1. **Classify the sample before touching it.** Determine what you have: MBR/VBR bootkit (first-sector code), UEFI bootkit (EFI application/driver or boot-variable manipulation), or kernel rootkit (driver/module, possibly hypervisor-level). Use `file`, hashes vs. intel, and the sample's origin (disk offset, EFI partition path, driver store location) to classify. Classification drives every later step — analyzing a UEFI sample with driver-analysis assumptions wastes days.
2. **Static analysis first — never boot the sample on hardware you care about.** Load the binary in Ghidra/IDA. For EFI binaries, note the subsystem, GUIDs, and protocol usage; for drivers, check imports (hooking-related APIs, disk/filter attach calls, network APIs) and embedded strings (C2 addresses, registry paths, service names, mutexes).
3. **Map the persistence mechanism precisely.** Answer *how it survives reboot*: modified MBR/VBR (compare against clean bytes), EFI boot variable changes (`BootOrder`/`Boot####` pointing at a rogue loader), a registered system driver/service, a kernel module in the initramfs, or SPI-flash modification. Document the exact hook point with offsets, names, or variable GUIDs — "it persists somehow" is not a finding.
4. **Identify the stealth technique.** Look for: SSDT/IDT hooking (legacy Windows), DKOM process/thread hiding, file-system minifilter attachment hiding files, NDIS/TDI-level network hiding, or hypervisor-level (Blue Pill style) subversion. Name the technique explicitly — it determines which telemetry can still see the malware and which is blind.
5. **Extract indicators systematically.** Collect: file hashes (sample and dropped components), driver/service names, registry keys (`HKLM\SYSTEM\CurrentControlSet\Services\`), EFI variable names and loader paths (`\EFI\...`), MBR/VBR byte signatures, mutexes, and network indicators. Separate high-confidence indicators (unique strings, unusual paths) from generic ones (common API imports) — only the former go into automated blocking.
6. **Compare against known-clean references.** Diff the suspect MBR/VBR bytes, EFI partition contents, and driver/module list against a clean reference of the same OS and firmware version. Unexplained deltas are your ground truth for "what the malware changed." Build these clean references *before* incidents, during provisioning.
7. **Dynamic analysis only if static is inconclusive — and only in a snapshot-isolated VM.** Enable kernel debugging or use a hypervisor-level tracer; boot the infected image; observe driver loads, registry writes, boot-variable changes, and network attempts (sinkholed). Revert the snapshot afterward and re-hash the lab VM to confirm it's clean. Never dynamic-test on bare metal you intend to reuse without a firmware reflash.
8. **Memory forensics for live confirmation.** If you have a memory image from an infected host, use Volatility to list kernel modules/drivers, check for hooked tables (SSDT, IDT), find hidden processes via pool-scanning vs. active-list comparison, and inspect driver objects. This confirms which static findings are actually active vs. dormant remnants.
9. **Write detection logic from findings.** Convert results into: EDR rules (driver-load events for identified names/hashes, EFI variable-change monitoring, service-creation events with kernel type), SIEM rules (unexpected `bcdedit` usage, firmware-update events outside change windows), and hunting queries (hosts with MBR hash ≠ fleet baseline, hosts with unknown EFI loaders). Include the clean-baseline values so analysts can tune without guessing.
10. **Plan remediation honestly.**
    Bootkits and kernel rootkits defeat in-OS cleaning tools — the malware
    sees the cleaner coming.
    Recommend reimaging from known-good media and, for UEFI bootkits,
    firmware reflash plus boot-variable reset per vendor procedure.
    Document *why* lesser remediation is insufficient; "run antivirus again"
    is not a plan for ring-0 malware.

## Key tools & commands

- Ghidra / IDA Free — disassembly of boot code, EFI binaries, and drivers;
  use version-appropriate loaders for PE32+ EFI images.
- `chipsec` (defensive firmware assessment) — verify platform firmware
  integrity where the platform is supported.
- Volatility (`windows.driverscan`, `linux.lsmod`, apihook plugins,
  `psxview` for hidden processes) — memory-resident confirmation.
- `bcdedit /enum firmware`, PowerShell EFI-variable reads — inspect boot
  configuration on Windows (read-only triage; do not modify during analysis).
- `dd` imaging of the MBR/VBR region
  (`dd if=/dev/sdX bs=512 count=1 | sha256sum`) compared against clean
  baselines.
- Trusted firmware-update utility from the hardware vendor — for the
  remediation reflash step.

## Expected outputs

- Sample classification, persistence mechanism, and stealth technique —
  each with evidence citations (offsets, names, variable GUIDs, disassembly
  references).
- IOC package: hashes, names, paths, registry keys, byte signatures,
  network indicators — tiered by confidence.
- Detection content: EDR/SIEM rules plus fleet baselines (clean MBR hashes,
  expected EFI loaders, known-good driver lists).
- Remediation recommendation with reimage/reflash rationale documented and
  vendor procedures referenced.

## Pitfalls

- Analyzing on the infected host with in-OS tools: a kernel rootkit lies to
  every API you call. Trust only offline disk analysis and
  hypervisor/memory-level views.
- Secure Boot presence ≠ safety: bootkits abuse stolen/leaked certificates,
  exploit signed-but-vulnerable bootloaders, or disable protections via
  physical access. Verify *which* binaries are signed and by whom, not just
  that signing is on.
- Attributing every unknown driver as malicious: cross-reference with vendor
  driver lists and intel before declaring — OEM updaters and security
  products install kernel drivers too.
- Forgetting the firmware: if the bootkit lives in SPI flash, reimaging the
  disk doesn't remove it. Scope remediation to the actual persistence layer
  from step 3.
- Snapshot complacency: reverting a VM snapshot doesn't clean a
  hypervisor-level rootkit that escaped to the host. Keep the lab host
  disposable and re-image it between high-risk analyses.

## References

- MITRE ATT&CK: T1542 (Pre-OS Boot: T1542.001 System Firmware, T1542.003
  Bootkit), T1014 (Rootkit), T1547.006 (Kernel Modules and Extensions)
- NIST SP 800-147 (BIOS protection) / SP 800-155 (BIOS integrity
  measurement) — firmware-integrity background
- Ghidra and Volatility documentation (analysis workflows)
- UEFI specification (EFI binary format, boot variables, Secure Boot) —
  reference for static analysis
- Vendor firmware-security guidance (Sure Start / SafeBIOS class features)
  for remediation options

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
