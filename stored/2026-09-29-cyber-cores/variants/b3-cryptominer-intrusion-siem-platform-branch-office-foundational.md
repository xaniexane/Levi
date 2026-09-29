---
skill_id: cyber_b3_cryptominer_intrusion_siem_platform_branch_office_foundational
name: Cryptominer Intrusion Defense for SIEM Platforms in Branch Offices (Foundational Maturity)
description: "Cryptominer Intrusion defense playbook for SIEM Platforms in Branch Offices at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [malware, cloud, soc, siem, monitoring, branch, network, maturity-foundational]
version: 1.0.0
---
# Cryptominer Intrusion Defense for SIEM Platforms in Branch Offices (Foundational Maturity)

## Purpose

Unauthorized miners burn CPU/GPU and cloud spend, and — more importantly — prove an attacker has code execution on your assets. Treat every miner as a foothold to investigate, not just a performance problem. Applies to SIEM Platforms in Branch Offices at Foundational maturity.

## When to use

- Sustained high CPU/GPU on hosts or cloud instances with no business workload, especially at night/weekends, plus connections to known mining pools on Stratum ports.
- Cloud billing spikes for compute in regions you do not use, or new instances launched by unfamiliar principals.
- EDR detections for xmrig or similar binaries, scheduled tasks re-fetching miner payloads, or WMI persistence entries.
- Lens: Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Detection rule hit history for the incident's indicators across the full retention window and Ingestion gap reports: which sources stopped logging and when (coverage blind spots); run `# conceptually (SIEM query languages differ):` then `index=* <indicator> earliest=-30d | stats count by sourcetype`.
3. **Analyze.** Trace the miner's persistence and delivery: the initial access vector (exposed service, weak SSH, vulnerable app) matters more than the miner itself. Then: Check for dual-use: many miner campaigns also exfiltrate credentials or deploy additional payloads — sweep for those.
4. **Contain and harden.** Close the entry vector (patch the exploited service, enforce key-based SSH, remove internet exposure), then block mining pool domains at DNS. Asset layer: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the miner without removing persistence — it returns on reboot or on schedule.
- Writing it off as 'just a miner' without investigating the initial access that delivered it.

## References

- MITRE ATT&CK: T1496 (Impact: Resource Hijacking)
- Vendor logging and hardening baselines for SIEM Platforms; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
