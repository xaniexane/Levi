---
skill_id: cyber_b3_mfa_fatigue_load_balancer_air_gapped_network_defined
name: MFA Fatigue Attack Defense for Load Balancers in Air-Gapped Networks (Defined Maturity)
description: "MFA Fatigue Attack defense playbook for Load Balancers in Air-Gapped Networks at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, network, web, air-gap, ot, high-security, maturity-defined]
version: 1.0.0
---
# MFA Fatigue Attack Defense for Load Balancers in Air-Gapped Networks (Defined Maturity)

## Purpose

Attackers with a stolen password spam push notifications until the victim approves one out of annoyance or confusion. The defense is push hygiene: number matching, context display, and rate limits on prompts. Applies to Load Balancers in Air-Gapped Networks at Defined maturity.

## When to use

- Dozens of MFA push prompts to one user in minutes, especially at odd hours, followed by a single approval.
- An approval immediately followed by session activity from an unusual IP or device enrollment changes.
- Helpdesk reports of users 'getting lots of MFA prompts' in the days before the incident.
- Lens: Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks and Backend pool changes and health-check failure histories; run `grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15` then `echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20`.
3. **Analyze.** Reconstruct the prompt storm: count, timing, and the approving event — then inventory the attacker's post-approval actions. Then: Check whether the attacker registered a new MFA method during the session (persistence via second factor).
4. **Contain and harden.** Number matching on all push MFA, show login context (app, location), and rate-limit prompts per user. Asset layer: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming an approved push means a legitimate user — approval is exactly what the attacker engineered.
- Not checking for newly registered MFA methods, which survive password resets.

## References

- MITRE ATT&CK: T1621 (Credential Access: MFA Request Generation)
- Vendor logging and hardening baselines for Load Balancers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
