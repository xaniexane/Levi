---
skill_id: cyber_b3_watering_hole_load_balancer_on_prem_datacenter_developing
name: Watering Hole Attack Defense for Load Balancers in On-Premises Datacenter (Developing Maturity)
description: "Watering Hole Attack defense playbook for Load Balancers in On-Premises Datacenter at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, web, on-prem, datacenter, maturity-developing]
version: 1.0.0
---
# Watering Hole Attack Defense for Load Balancers in On-Premises Datacenter (Developing Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to Load Balancers in On-Premises Datacenter at Developing maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks and Backend pool changes and health-check failure histories; run `grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15` then `echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for Load Balancers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
