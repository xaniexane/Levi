---
skill_id: cyber_b3_insider_data_theft_ot_controller_air_gapped_network_optimized
name: Insider Data Theft Defense for OT Controllers in Air-Gapped Networks (Optimized Maturity)
description: "Insider Data Theft defense playbook for OT Controllers in Air-Gapped Networks at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, ot, ics, critical-infrastructure, air-gap, high-security, maturity-optimized]
version: 1.0.0
---
# Insider Data Theft Defense for OT Controllers in Air-Gapped Networks (Optimized Maturity)

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. Applies to OT Controllers in Air-Gapped Networks at Optimized maturity.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context
- Vendor logging and hardening baselines for OT Controllers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
