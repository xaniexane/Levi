---
skill_id: cyber_b3_log_tampering_saas_application_colocation_facility_managed
name: Log Tampering Defense for SaaS Applications in Colocation Facilities (Managed Maturity)
description: "Log Tampering defense playbook for SaaS Applications in Colocation Facilities at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, cloud, saas, identity, on-prem, colocation, maturity-managed]
version: 1.0.0
---
# Log Tampering Defense for SaaS Applications in Colocation Facilities (Managed Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to SaaS Applications in Colocation Facilities at Managed maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: SaaS audit logs (admin + user activity) streamed to SIEM + SSO logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Admin audit log (settings changes, user provisioning, sharing changes) and User activity logs: file access, downloads, external sharing events; run `# conceptually (SaaS APIs differ):` then `saas-cli audit log --category admin --last 7d --format table | head -25`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: SSO with MFA enforced, SCIM provisioning, least-privilege roles, external-sharing restricted. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for SaaS Applications; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
