---
skill_id: cyber_performing_plc_firmware_security_analysis
name: PLC Firmware Security Analysis
description: Analyze PLC firmware for vulnerabilities, backdoors, and insecure defaults to protect industrial control systems.
risk: low
permissions: []
requires_confirmation: false
tags: [ot, firmware, plc]
version: 1.0.0
---

## Purpose
- Determine whether PLC firmware contains vulnerabilities, hardcoded credentials, or malicious modifications.
- Support procurement and vendor risk decisions with evidence about firmware security posture.
- Build detection and hardening guidance for the specific firmware versions running in the plant.

## When to use
- When onboarding a new PLC vendor or firmware version into the control environment.
- When threat intelligence reports firmware-level compromise of similar industrial devices.
- During incident response when a controller is suspected of being tampered with.
- As part of a supply-chain security review for critical control assets.

## Prerequisites
- Firmware images obtained legitimately from the vendor or extracted from a spare device, never from a live controller.
- An isolated analysis lab with firmware analysis tooling: binwalk, Ghidra or IDA, and strings utilities.
- Vendor documentation, release notes, and known CVE lists for the firmware version.
- Operations approval for any activity involving production devices, with a strict no-touch default.

## Procedure
1. Record firmware provenance: source, version, hash, and which devices in the fleet run it.
2. Extract the filesystem and binaries from the firmware image using binwalk or vendor-provided tools.
3. Inventory services, open ports, and management interfaces exposed by the firmware.
4. Search for hardcoded credentials, default passwords, private keys, and debug interfaces left enabled.
5. Compare the firmware against a vendor-supplied known-good image to detect unauthorized modifications.
6. Analyze network services for known-vulnerable software versions and insecure protocol implementations.
7. Check update mechanisms: signature verification, rollback protection, and transport security.
8. Review vendor advisories and CVEs for the firmware version and confirm applicability to the extracted build.
9. Document findings with severity, exploitability, and operational constraints on remediation.
10. Recommend hardening: disable unused services, change defaults, segment management access, and plan firmware updates within maintenance windows.

## Expected outputs
- A firmware security report with findings, severity ratings, and evidence.
- Hardening guidance specific to the firmware version and deployment.
- Vendor follow-up items for confirmed vulnerabilities.
- A firmware bill of materials for the analyzed version to support future vulnerability tracking.
- Procurement language requiring signed firmware and vulnerability disclosure from vendors.

## Pitfalls
- Extracting firmware from a live production controller, which risks process disruption.
- Declaring firmware clean because automated tools found nothing; manual review of services and credentials is essential.
- Recommending immediate patching without checking vendor support and maintenance windows.

## References
- ISA Secure product certification references
- NIST SP 800-82 Guide to OT Security
- CISA ICS advisories
- NIST SP 800-193 Platform Firmware Resiliency Guidelines
- Vendor firmware security documentation and advisories
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
