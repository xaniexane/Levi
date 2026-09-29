---
skill_id: cyber_b3_session_hijacking_load_balancer_air_gapped_network_developing
name: Web Session Hijacking Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)
description: "Web Session Hijacking defense playbook for Load Balancers in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, identity, network, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Web Session Hijacking Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)

## Purpose

Stolen session cookies let attackers ride authenticated web sessions without credentials or MFA. Cookie theft via infostealer or XSS is the usual source; concurrent-session anomalies are the usual signal. Applies to Load Balancers in Air-Gapped Networks at Developing maturity.

## When to use

- The same session active from two geographies or ASNs simultaneously, or a session suddenly continuing from a datacenter IP.
- Session created without a fresh authentication event (cookie replay), or user-agent/IP changing mid-session.
- Infostealer execution on the user's device shortly before the anomalous session.
- Lens: Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks and Backend pool changes and health-check failure histories; run `grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15` then `echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20`.
3. **Analyze.** Determine the theft vector: device compromise (cookie files exfiltrated) versus application XSS — the fix differs. Then: Inventory actions taken in the hijacked session: data viewed, settings changed, transactions performed.
4. **Contain and harden.** Short session lifetimes, binding sessions to device/IP characteristics, and step-up auth for sensitive actions. Asset layer: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Invalidating the password but not the session — the hijacker stays logged in.
- Missing that the user's DEVICE is compromised; the next session gets stolen too until the infostealer is removed.

## References

- MITRE ATT&CK: T1539 (Credential Access: Steal Web Session Cookie)
- Vendor logging and hardening baselines for Load Balancers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
