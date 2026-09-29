---
skill_id: cyber_b3_insider_data_theft_siem_platform_branch_office_developing
name: Insider Data Theft Defense for SIEM Platforms in Branch Offices (Developing Maturity)
description: "Insider Data Theft defense playbook for SIEM Platforms in Branch Offices at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, soc, siem, monitoring, branch, network, maturity-developing]
version: 1.0.0
---
# Insider Data Theft Defense for SIEM Platforms in Branch Offices (Developing Maturity)

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. Applies to SIEM Platforms in Branch Offices at Developing maturity.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.
- Lens: Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Detection rule hit history for the incident's indicators across the full retention window and Ingestion gap reports: which sources stopped logging and when (coverage blind spots); run `# conceptually (SIEM query languages differ):` then `index=* <indicator> earliest=-30d | stats count by sourcetype`.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Asset layer: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context
- Vendor logging and hardening baselines for SIEM Platforms; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
