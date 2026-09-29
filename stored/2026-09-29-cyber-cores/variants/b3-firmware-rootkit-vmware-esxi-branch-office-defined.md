---
skill_id: cyber_b3_firmware_rootkit_vmware_esxi_branch_office_defined
name: Firmware Rootkit Defense for VMware ESXi Hosts in Branch Offices (Defined Maturity)
description: "Firmware Rootkit defense playbook for VMware ESXi Hosts in Branch Offices at Defined maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [firmware, persistence, virtualization, vmware, branch, network, maturity-defined]
version: 1.0.0
---
# Firmware Rootkit Defense for VMware ESXi Hosts in Branch Offices (Defined Maturity)

## Purpose

Malware in UEFI/BIOS or device firmware survives OS reinstalls and disk replacements. Rare but devastating — detection needs firmware measurement (TPM attestation) and dedicated scanning, not standard AV. Applies to VMware ESXi Hosts in Branch Offices at Defined maturity.

## When to use

- CHIPSEC or firmware-scanner findings of modified UEFI modules, unexpected DXE drivers, or Secure Boot disabled without authorization.
- TPM attestation failures or PCR values deviating from the known-good baseline for the hardware model.
- Persistence surviving full disk wipe and OS reinstall — the hallmark symptom.
- Lens: Best telemetry: vCenter tasks/events + ESXi syslog + lockdown-mode audit. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in vCenter tasks and events (VM power ops, snapshot create/delete, host profile changes) and ESXi hostd/vpxa logs and shell-access records; VM .vmx changes; run `esxcli system auditrecords local list | tail -20` then `vim-cmd vmsvc/getallvms 2>/dev/null | head -20`.
3. **Analyze.** Dump the firmware image (with authorization) and diff against the vendor's known-good image for the exact board and version. Then: Determine the implant's capabilities: network, persistence mechanism, and whether it targets other hosts (some spread via firmware update mechanisms).
4. **Contain and harden.** Enable Secure Boot + TPM measured boot fleet-wide; lock BIOS with admin passwords and signed firmware updates only. Asset layer: Lockdown mode on, isolated management network, unique per-host root passwords, MFA on vCenter. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reinstalling the OS repeatedly while the firmware implant re-infects each build.
- Running firmware scans from the potentially compromised OS — use offline/BIOS-level tooling.

## References

- MITRE ATT&CK: T1542 (Persistence: Pre-OS Boot: System Firmware)
- Vendor logging and hardening baselines for VMware ESXi Hosts; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
