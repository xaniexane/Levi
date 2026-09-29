---
skill_id: cyber_b3_log_tampering_api_gateway_azure_cloud_optimized
name: Log Tampering Defense for API Gateways in Azure Cloud (Optimized Maturity)
description: "Log Tampering defense playbook for API Gateways in Azure Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, web, api, cloud, azure, maturity-optimized]
version: 1.0.0
---
# Log Tampering Defense for API Gateways in Azure Cloud (Optimized Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to API Gateways in Azure Cloud at Optimized maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for API Gateways; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
