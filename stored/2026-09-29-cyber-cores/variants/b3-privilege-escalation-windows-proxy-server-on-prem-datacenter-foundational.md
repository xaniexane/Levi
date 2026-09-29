---
skill_id: cyber_b3_privilege_escalation_windows_proxy_server_on_prem_datacenter_foundational
name: Windows Privilege Escalation Defense for Proxy Servers in On-Premises Datacenter (Foundational Maturity)
description: "Windows Privilege Escalation defense playbook for Proxy Servers in On-Premises Datacenter at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, network, proxy, web, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# Windows Privilege Escalation Defense for Proxy Servers in On-Premises Datacenter (Foundational Maturity)

## Purpose

From standard user to SYSTEM/Administrator via unquoted service paths, writable service binaries, AlwaysInstallElevated, token manipulation, or kernel exploits. Windows privesc is usually a misconfiguration the attacker read, not a zero-day they brought. Applies to Proxy Servers in On-Premises Datacenter at Foundational maturity.

## When to use

- Service creation or modification events (7045/4697) pointing at user-writable paths, or processes spawning as SYSTEM from unexpected parents.
- Registry writes to AlwaysInstallElevated keys, accessibility binary replacement (sethc/utilman), or token duplication API patterns in EDR telemetry.
- Enumeration tooling: whoami /priv, accesschk, or PowerShell privesc scripts running before the escalation.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Pin down the primitive: unquoted path, weak service ACL, scheduled task with stored creds, or kernel CVE — then check how many fleet hosts share it. Then: Review what the elevated access touched: SAM/LSASS access after escalation means credential theft followed.
4. **Contain and harden.** Fix service ACLs and paths fleet-wide, disable AlwaysInstallElevated, and enforce signed-driver and LSA protection policies. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reimaging one host while the GPO-deployed misconfiguration recreates the hole on every rebuild.
- Missing that the attacker already dumped credentials post-escalation — scope the follow-on theft, not just the privesc.

## References

- MITRE ATT&CK: T1068 (Privilege Escalation: Exploitation for Privilege Escalation)
- Vendor logging and hardening baselines for Proxy Servers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
