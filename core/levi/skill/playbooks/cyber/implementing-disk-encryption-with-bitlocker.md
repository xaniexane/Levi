---
skill_id: cyber_implementing_disk_encryption_with_bitlocker
name: Disk Encryption with BitLocker
description: Roll out BitLocker full-disk encryption with backed-up recovery keys and compliance reporting.
risk: moderate
permissions: []
requires_confirmation: true
tags: [endpoint, encryption]
version: 1.0.0
---
## Purpose
Lost or stolen laptops with unencrypted disks are data breaches — full stop. BitLocker provides
Windows full-disk encryption integrated with TPM, manageable at scale via Group Policy or Intune.
This playbook rolls it out across the fleet with recovery-key escrow, TPM requirements, and
compliance monitoring. Confirmation is required: encryption changes affect every endpoint, and
misconfiguration can lock users out.

## When to use
- Meeting encryption requirements for data at rest (HIPAA, PCI DSS, GDPR, CMMC).
- After incidents involving lost/stolen devices with unencrypted drives.
- As a baseline control in any Windows endpoint security program.
- Before handling regulated data on laptops or portable media.
- Alongside device-posture assessment: encryption status feeds compliance verdicts.

## Prerequisites
- TPM 1.2+ (2.0 preferred) on all target devices — verify fleet TPM status first; devices without
  TPM need a plan (upgrade, exception, or alternative).
- Recovery-key escrow: Active Directory or Entra ID configured to store recovery keys (mandatory —
  no escrow, no rollout).
- Group Policy or Intune for configuration deployment and compliance reporting.
- Defined encryption standard: XTS-AES 256-bit for OS and fixed drives (set explicitly, don't accept
  defaults blindly).
- User communication: what BitLocker is, when they'll see prompts, and how recovery works.

## Procedure
1. **Verify TPM and hardware readiness.** Audit the fleet: TPM version and status, BIOS/UEFI mode,
   and Secure Boot state. Remediate: enable TPM in BIOS via vendor tools, update TPM firmware where
   needed. Devices that can't meet the hardware bar get a documented exception path or replacement
   plan — not a silent skip.
2. **Configure recovery-key escrow first.** Set up AD/Entra ID backup of recovery keys and
   passwords; verify with a pilot device that keys actually land in the directory and are
   retrievable by authorized helpdesk roles only. Test the full recovery flow end-to-end before
   broad deployment. Escrow failure means permanent data loss on recovery events.
3. **Define the encryption policy.** Via GPO/Intune: require TPM + PIN for OS drives on high-risk
   populations (or TPM-only where UX demands, documented as a risk decision), XTS-AES-256, deny
   write access to unencrypted removable drives, and require encryption on fixed data drives.
   Require, don't merely allow.
4. **Pilot with IT.** Enable on IT devices first: validate policy application, measure encryption
   time and performance impact, exercise recovery (simulate PIN loss), and confirm helpdesk can
   retrieve escrowed keys. Fix policy issues here, not on executives' laptops.
5. **Roll out in waves.** By department or device cohort: enable encryption, monitor compliance
   reporting, and support users through initial encryption (which takes time — schedule it, don't
   surprise). Track per-wave compliance percent; don't start the next wave until the current one is
   green.
6. **Enforce pre-boot authentication appropriately.** For high-risk users/devices: TPM+PIN. For
   general population: TPM-only may be acceptable with documented risk acceptance — but understand
   the tradeoff (DMA attacks, stolen-while-running scenarios). Never allow BitLocker without TPM on
   capable hardware.
7. **Monitor compliance continuously.** Report: percent of fleet encrypted, devices with escrowed
   keys (must equal encrypted count — investigate gaps immediately), encryption algorithm
   compliance, and removable-media policy status. Alert on: devices reporting unencrypted, escrow
   failures, and BitLocker being suspended/disabled.
8. **Harden against bypasses.** Enable Secure Boot, set BIOS/UEFI passwords, disable boot from
   external media, and consider DMA protection (Kernel DMA Protection / Thunderbolt restrictions).
   BitLocker's strength depends on the pre-boot chain — an attacker who boots their own OS bypasses
   it.
9. **Manage the recovery process.** Document: who can retrieve recovery keys (helpdesk role,
   MFA-required, logged), identity verification before key release, and key-rotation after recovery
   use (a used recovery key scenario should trigger re-encryption key rotation per policy). Audit
   key retrievals quarterly.
10. **Handle lifecycle events.** Device decommission: cryptographic erase (destroy keys) or full
    wipe. Device transfer: decrypt/re-encrypt with new ownership. TPM changes (motherboard
    replacement): plan for recovery-key need. Each lifecycle event has a documented encryption step
    — gaps here are where unencrypted disks appear.

## Expected outputs
- BitLocker enforced fleet-wide (XTS-AES-256, TPM-backed) with wave rollout evidence.
- Recovery keys escrowed in AD/Entra ID with tested retrieval and audited access.
- Compliance dashboards: encryption percent, escrow coverage, algorithm compliance.
- Pre-boot hardening (Secure Boot, BIOS passwords, DMA protection) and removable-media policy.
- Lifecycle procedures covering decommission, transfer, and hardware-change scenarios.

## Pitfalls
- No escrow: the first forgotten PIN becomes permanent data loss. Escrow tested before rollout, no
  exceptions.
- Skipping the pilot: policy mistakes at fleet scale mean mass recovery events. IT pilots first,
  always.
- TPM-only without risk acknowledgment: convenient but weaker against physical attacks. Make it an
  explicit, documented decision per population.
- Ignoring pre-boot chain: BitLocker without Secure Boot and BIOS controls is encryption with the
  back door open.
- Removable media forgotten: encrypted laptops with unencrypted USB drives full of exports. Policy
  must cover removable media.

## References
- Microsoft Learn: BitLocker documentation (deployment, GPO/Intune management, recovery)
- NIST SP 800-111 (storage encryption technologies)
- CIS Microsoft Windows benchmarks (BitLocker configuration)
- NIST SP 800-53 SC-12, SC-28 (cryptographic key management, protection at rest)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
