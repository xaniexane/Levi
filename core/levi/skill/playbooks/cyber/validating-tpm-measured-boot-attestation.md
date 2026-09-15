---
skill_id: cyber_validating_tpm_measured_boot_attestation
name: Validating TPM Measured Boot Attestation
description: Validate TPM-based measured boot and remote attestation to detect bootkits and firmware tampering.
risk: info
permissions: []
requires_confirmation: false
tags: [hardware, tpm, attestation]
version: 1.0.0
---
## Purpose
TPM measured boot records each boot component's hash into Platform Configuration Registers, and remote attestation lets a verifier check those measurements against known-good values. This playbook validates that chain: confirming measured boot is enabled, establishing golden measurements, and using attestation to detect bootkits, firmware tampering, or unauthorized bootloaders.

## When to use
- Deploying Secure Boot/measured boot standards for endpoints or servers.
- Investigating suspected bootkit or firmware-level compromise.
- High-assurance environments requiring boot integrity evidence.
- Validating hardware supply-chain integrity on new devices.

## Prerequisites
- Devices with TPM 2.0 and UEFI Secure Boot capability.
- Attestation infrastructure or tooling (OS-native or third-party verifier).
- Golden measurements for approved firmware, bootloader, and OS combinations.
- Baseline of current boot configurations across the fleet.

## Procedure
1. Confirm TPM 2.0 is present, enabled, and owned; verify Secure Boot is on and in the correct mode.
2. Enable measured boot so each stage (firmware, bootloader, kernel) extends PCRs.
3. Capture golden PCR values for each approved hardware/firmware/OS combination in the fleet.
4. Configure remote attestation: devices quote PCRs to a verifier on boot and on schedule.
5. Build alerting for attestation failures: unknown PCR values, disabled TPM, or Secure Boot off.
6. During investigations, compare a suspect device's measurements against golden values to identify tampered stages.
7. Protect the golden values and verifier keys; compromise there undermines the whole chain.
8. Re-baseline golden measurements through a controlled process on every approved firmware/OS update.
9. Extend attestation coverage to container hosts and hypervisors, not just endpoints.
10. Source golden measurements from the vendor through a secure channel; supply-chain attacks poison them.
11. Test the incident workflow for attestation failures before relying on it.

## Expected outputs
- Measured-boot enablement status across the fleet.
- Golden measurement registry per approved configuration.
- Attestation monitoring with alerting on deviations.
- Attestation coverage map across device classes.
- Golden-measurement sourcing records.
- Attestation-failure incident workflow test results.

## Pitfalls
- Firmware updates change PCRs; without a re-baselining process every update looks like an attack.
- Attestation verifies measurement, not goodness; golden values must come from trusted sources.
- TPM ownership and endorsement-key validation are often skipped; verify the TPM is genuine.
- Virtualized TPMs have different trust properties; document which environments use vTPMs.
- Firmware supply-chain attacks can poison golden measurements; source them securely.
- Attestation without a tested response workflow is just logging.
- Physical attackers with TPM reset capabilities need additional controls; know the limits.
- Measured boot gaps in the option ROM stage are a real blind spot; know your platform's coverage.

## References
- Trusted Computing Group: TPM 2.0 and measured boot specifications.
- NIST SP 800-155 (BIOS integrity) and SP 800-193 (platform firmware resilience).
- Microsoft Learn: TPM and measured boot attestation.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
