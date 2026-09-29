---
skill_id: cyber_b3_password_spraying_ot_controller_hybrid_cloud_managed
name: Password Spraying Defense for OT Controllers in Hybrid Cloud (Managed Maturity)
description: "Password Spraying defense playbook for OT Controllers in Hybrid Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, ot, ics, critical-infrastructure, hybrid, cloud, on-prem, maturity-managed]
version: 1.0.0
---
# Password Spraying Defense for OT Controllers in Hybrid Cloud (Managed Maturity)

## Purpose

Attackers try a small set of common passwords against many usernames, staying under per-account lockout thresholds. It is quieter than stuffing and specifically tuned to evade lockout policies, often running for days or weeks. Applies to OT Controllers in Hybrid Cloud at Managed maturity.

## When to use

- A handful of failed logons per account (1-3) spread across hundreds of accounts from one or a few IPs, repeating on a schedule — the classic low-and-slow pattern.
- The same few passwords attempted everywhere (SeasonYear!, Company123, Password1); check by aggregating failed-logon password hashes where your IdP logs them.
- Spray bursts correlated with newly published password lists or timed to holidays/weekends when response is slower.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Reconstruct the spray window: first-seen to last-seen per source IP, and list every account with even one success inside the window — those are confirmed or suspected takeovers. Then: Check whether sprayed accounts share traits (same OU, same onboarding batch, service accounts) to find how the username list was built.
4. **Contain and harden.** Smart lockout (soft lockout with increasing delays) plus alerting on distributed low-volume failures, not just lockouts. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Per-account lockout thresholds alone will not catch spraying; you need cross-account velocity detection.
- Treating one success as an isolated incident misses the campaign — always scope the full spray window.

## References

- MITRE ATT&CK: T1110.003 (Credential Access: Brute Force: Password Spraying)
- Vendor logging and hardening baselines for OT Controllers; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
