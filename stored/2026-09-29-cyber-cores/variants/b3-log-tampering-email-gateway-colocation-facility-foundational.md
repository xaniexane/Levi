---
skill_id: cyber_b3_log_tampering_email_gateway_colocation_facility_foundational
name: Log Tampering Defense for Email Gateways in Colocation Facilities (Foundational Maturity)
description: "Log Tampering defense playbook for Email Gateways in Colocation Facilities at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, email, phishing, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Log Tampering Defense for Email Gateways in Colocation Facilities (Foundational Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to Email Gateways in Colocation Facilities at Foundational maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Message tracking (sender, recipients, subject hash, attachments, verdicts) for the campaign window and Sandbox detonation reports for attachments/URLs; quarantined message copies; run `# conceptually (gateway CLIs differ):` then `message-tracking --sender <suspect-domain> --last 7d`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for Email Gateways; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
