---
skill_id: cyber_b3_insider_data_theft_mobile_device_mdm_on_prem_datacenter_foundational
name: Insider Data Theft Defense for Mobile Devices (MDM) in On-Premises Datacenter (Foundational Maturity)
description: "Insider Data Theft defense playbook for Mobile Devices (MDM) in On-Premises Datacenter at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [insider, dlp, mobile, mdm, endpoint, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# Insider Data Theft Defense for Mobile Devices (MDM) in On-Premises Datacenter (Foundational Maturity)

## Purpose

A trusted user steals data — often before resignation. Unlike external attacks there is no malware to find; detection relies on behavioral baselines: access volume, off-hours activity, and personal-storage uploads. Handle with HR and legal from the start. Applies to Mobile Devices (MDM) in On-Premises Datacenter at Foundational maturity.

## When to use

- A user accessing far more files or records than their role baseline, especially in the 30 days before resignation or termination.
- Bulk downloads to USB, personal cloud uploads, or emailing attachments to personal addresses from a corporate account.
- Off-hours access to repositories the user never touched before, or permission changes granting themselves broader access.
- Lens: Best telemetry: MDM compliance/app inventory + mobile threat defense alerts + enrollment logs. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in MDM device inventory: OS versions, jailbreak/root detections, installed app lists and Mobile threat defense alerts (malicious apps, network attacks, OS tampering); run `# conceptually (MDM APIs differ):` then `mdm-cli devices list --noncompliant --limit 30`.
3. **Analyze.** Build a 90-day access timeline for the user: volume, data sensitivity, destination (USB serial, cloud account, personal email) — coordinate collection with HR/legal to stay compliant. Then: Determine business justification for each anomaly with the user's manager before concluding malice; over-collection without cause creates liability.
4. **Contain and harden.** UEBA baselines with alerting on pre-resignation access spikes; disable USB mass storage or enforce encryption + logging. Asset layer: Enrollment required for corporate data, OS version minimums, jailbreak/root = automatic quarantine. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Investigating without HR/legal involvement — privacy and employment law exposure is real.
- Confronting the user before evidence is preserved; they will delete local copies first.

## References

- MITRE ATT&CK: T1005 (Collection: Data from Local System) — insider context
- Vendor logging and hardening baselines for Mobile Devices (MDM); Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
