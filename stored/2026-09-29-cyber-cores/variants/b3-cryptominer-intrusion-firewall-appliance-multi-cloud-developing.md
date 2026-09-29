---
skill_id: cyber_b3_cryptominer_intrusion_firewall_appliance_multi_cloud_developing
name: Cryptominer Intrusion Defense for Firewall Appliances in Multi-Cloud (Developing Maturity)
description: "Cryptominer Intrusion defense playbook for Firewall Appliances in Multi-Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [malware, cloud, network, firewall, multi-cloud, maturity-developing]
version: 1.0.0
---
# Cryptominer Intrusion Defense for Firewall Appliances in Multi-Cloud (Developing Maturity)

## Purpose

Unauthorized miners burn CPU/GPU and cloud spend, and — more importantly — prove an attacker has code execution on your assets. Treat every miner as a foothold to investigate, not just a performance problem. Applies to Firewall Appliances in Multi-Cloud at Developing maturity.

## When to use

- Sustained high CPU/GPU on hosts or cloud instances with no business workload, especially at night/weekends, plus connections to known mining pools on Stratum ports.
- Cloud billing spikes for compute in regions you do not use, or new instances launched by unfamiliar principals.
- EDR detections for xmrig or similar binaries, scheduled tasks re-fetching miner payloads, or WMI persistence entries.
- Lens: Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log and Configuration revisions and diffs; VPN session logs and authentication failures; run `# vendor CLIs differ; conceptually:` then `show log traffic query (source <suspect-ip>)             # Palo Alto style`.
3. **Analyze.** Trace the miner's persistence and delivery: the initial access vector (exposed service, weak SSH, vulnerable app) matters more than the miner itself. Then: Check for dual-use: many miner campaigns also exfiltrate credentials or deploy additional payloads — sweep for those.
4. **Contain and harden.** Close the entry vector (patch the exploited service, enforce key-based SSH, remove internet exposure), then block mining pool domains at DNS. Asset layer: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the miner without removing persistence — it returns on reboot or on schedule.
- Writing it off as 'just a miner' without investigating the initial access that delivered it.

## References

- MITRE ATT&CK: T1496 (Impact: Resource Hijacking)
- Vendor logging and hardening baselines for Firewall Appliances; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
