---
skill_id: cyber_b3_log_tampering_vpn_gateway_remote_workforce_defined
name: Log Tampering Defense for VPN Gateways in Remote Workforce (Defined Maturity)
description: "Log Tampering defense playbook for VPN Gateways in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, defense-evasion, network, vpn, remote-access, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Log Tampering Defense for VPN Gateways in Remote Workforce (Defined Maturity)

## Purpose

Attackers clear or alter logs to blind defenders — event log clears, audit policy disabling, or timestomping. The tampering itself is evidence: treat cleared logs as confirmation of malicious activity, not as missing data. Applies to VPN Gateways in Remote Workforce at Defined maturity.

## When to use

- Event 1102 (audit log cleared) or 104 (log cleared), audit policy changes disabling categories, or gaps in otherwise continuous log streams.
- Timestomped files (MFT timestamps inconsistent with sequence numbers) or syslog gaps from specific hosts.
- SIEM agent uninstalls or forwarding configuration changes.
- Lens: Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in VPN auth logs (success/failure per user with source IPs), session tables with data volumes and Gateway admin audit log and firmware/patch version; client version inventory; run `# conceptually (vendor CLIs differ):` then `show vpn-sessiondb detail anyconnect | grep -E 'Username|Assigned IP|Login Time'`.
3. **Analyze.** The clear event's timestamp bounds the attacker's active window — focus forensic effort just before it. Then: Recover from redundant sources: EDR cloud telemetry, network logs, and central syslog often survive local clears.
4. **Contain and harden.** Forward logs off-host in real time to tamper-evident central storage; alert on 1102/104 immediately. Asset layer: MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating 'no logs' as 'no evidence of compromise' — absence after tampering IS the evidence.
- Relying solely on host logs; always have an independent telemetry path (network, EDR cloud).

## References

- MITRE ATT&CK: T1070 (Defense Evasion: Indicator Removal)
- Vendor logging and hardening baselines for VPN Gateways; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
