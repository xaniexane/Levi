---
skill_id: cyber_b3_firmware_rootkit_azure_subscription_azure_cloud_defined
name: Firmware Rootkit Defense for Azure Subscriptions in Azure Cloud (Defined Maturity)
description: "Firmware Rootkit defense playbook for Azure Subscriptions in Azure Cloud at Defined maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [firmware, persistence, cloud, azure, maturity-defined]
version: 1.0.0
---
# Firmware Rootkit Defense for Azure Subscriptions in Azure Cloud (Defined Maturity)

## Purpose

Malware in UEFI/BIOS or device firmware survives OS reinstalls and disk replacements. Rare but devastating — detection needs firmware measurement (TPM attestation) and dedicated scanning, not standard AV. Applies to Azure Subscriptions in Azure Cloud at Defined maturity.

## When to use

- CHIPSEC or firmware-scanner findings of modified UEFI modules, unexpected DXE drivers, or Secure Boot disabled without authorization.
- TPM attestation failures or PCR values deviating from the known-good baseline for the hardware model.
- Persistence surviving full disk wipe and OS reinstall — the hallmark symptom.
- Lens: Best telemetry: Activity Log + Entra sign-in logs + Defender for Cloud + NSG flow logs. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Azure Activity Log (write/delete on IAM, policy, network) and Entra audit/sign-in logs and Defender for Cloud recommendations and alerts; resource-change history; run `az monitor activity-log list --max-events 25 --query '[].{time:eventTimestamp, op:operationName.value, caller:caller}' -o table` then `az security alert list --query '[].{name:alertDisplayName, severity:severity, time:timeGeneratedUtc}' -o table`.
3. **Analyze.** Dump the firmware image (with authorization) and diff against the vendor's known-good image for the exact board and version. Then: Determine the implant's capabilities: network, persistence mechanism, and whether it targets other hosts (some spread via firmware update mechanisms).
4. **Contain and harden.** Enable Secure Boot + TPM measured boot fleet-wide; lock BIOS with admin passwords and signed firmware updates only. Asset layer: Azure Policy deny-effects on public storage/exposure; PIM for subscription roles; Defender plans on. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reinstalling the OS repeatedly while the firmware implant re-infects each build.
- Running firmware scans from the potentially compromised OS — use offline/BIOS-level tooling.

## References

- MITRE ATT&CK: T1542 (Persistence: Pre-OS Boot: System Firmware)
- Vendor logging and hardening baselines for Azure Subscriptions; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
