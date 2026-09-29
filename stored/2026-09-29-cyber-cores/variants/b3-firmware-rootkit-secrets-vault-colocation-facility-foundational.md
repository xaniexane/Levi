---
skill_id: cyber_b3_firmware_rootkit_secrets_vault_colocation_facility_foundational
name: Firmware Rootkit Defense for Secrets Vaults in Colocation Facilities (Foundational Maturity)
description: "Firmware Rootkit defense playbook for Secrets Vaults in Colocation Facilities at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [firmware, persistence, secrets, identity, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Firmware Rootkit Defense for Secrets Vaults in Colocation Facilities (Foundational Maturity)

## Purpose

Malware in UEFI/BIOS or device firmware survives OS reinstalls and disk replacements. Rare but devastating — detection needs firmware measurement (TPM attestation) and dedicated scanning, not standard AV. Applies to Secrets Vaults in Colocation Facilities at Foundational maturity.

## When to use

- CHIPSEC or firmware-scanner findings of modified UEFI modules, unexpected DXE drivers, or Secure Boot disabled without authorization.
- TPM attestation failures or PCR values deviating from the known-good baseline for the hardware model.
- Persistence surviving full disk wipe and OS reinstall — the hallmark symptom.
- Lens: Best telemetry: secret access audit (who read what, when) + policy-change audit + unseal events. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Audit log of secret reads/writes/deletes with client identity and source IP and Policy and auth-method changes; root-token generation events; run `vault audit log --since 24h 2>/dev/null | grep -E '"path":"secret' | head -20` then `vault list sys/policy 2>/dev/null; vault auth list 2>/dev/null`.
3. **Analyze.** Dump the firmware image (with authorization) and diff against the vendor's known-good image for the exact board and version. Then: Determine the implant's capabilities: network, persistence mechanism, and whether it targets other hosts (some spread via firmware update mechanisms).
4. **Contain and harden.** Enable Secure Boot + TPM measured boot fleet-wide; lock BIOS with admin passwords and signed firmware updates only. Asset layer: Short-lived dynamic secrets, no static long-lived tokens, MFA on UI access, sealed storage backend. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reinstalling the OS repeatedly while the firmware implant re-infects each build.
- Running firmware scans from the potentially compromised OS — use offline/BIOS-level tooling.

## References

- MITRE ATT&CK: T1542 (Persistence: Pre-OS Boot: System Firmware)
- Vendor logging and hardening baselines for Secrets Vaults; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
