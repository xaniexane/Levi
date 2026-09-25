---
skill_id: cyber_detecting_port_scanning_with_fail2ban
name: Detecting Port Scanning with Fail2ban
description: Use Fail2ban to detect port scans and automatically block scanning sources.
risk: low
permissions: []
requires_confirmation: false
tags: [fail2ban, ids, linux]
version: 1.0.0
---
## Purpose

Fail2ban is best known for brute-force blocking, but its log-monitoring and threshold engine also makes a serviceable lightweight scan detector for Linux hosts and small networks. This playbook covers configuring Fail2ban to detect port-scanning behavior from firewall/kernel logs and respond with automatic blocks — plus the limits of this approach.

## When to use

- You run Linux servers and need lightweight scan detection without a full IDS.
- Perimeter logs show persistent scanning and you want automatic blocking.
- Small-business or lab environments needing low-maintenance protection.
- Complementing a network IDS with host-level scan response.

## Prerequisites

- Fail2ban installed on the Linux host(s); firewall logs (iptables/nftables LOG targets, or firewalld rich-logging) as the monitored log source.
- Root/sudo access to configure jails and actions.
- Inventory of legitimate scanners (vuln management, monitoring) to whitelist.
- Understanding of your firewall's log format for writing accurate failregex patterns.

## Procedure

1. Feed firewall logs to Fail2ban. Configure your firewall to log dropped/rejected packets with a recognizable prefix, and point a Fail2ban filter at that log. Write failregex patterns matching your log format (test with fail2ban-regex before deploying) — the pattern must extract the source IP reliably across IPv4 and IPv6.
2. Define scan-detection jails with appropriate thresholds. Create jails that trigger on: many distinct dropped ports from one IP in a short window (port scan), and repeated connection attempts to closed/filtered ports. Set findtime/maxretry to match scan behavior (e.g., 20+ distinct ports within 60-300 seconds) — thresholds too low block legitimate clients hitting a closed port once.
3. Whitelist deliberately. Add vulnerability scanners, monitoring systems, and CDN/proxy egress ranges to ignoreip — but scope narrowly and review periodically. Never whitelist broad ranges 'to stop the alerts'; a too-broad ignoreip is a hole, not tuning.
4. Choose blocking actions proportional to the asset. For internet-facing servers, temporary blocks (hours, escalating with recidive) are standard. For internal hosts, alert rather than auto-block — blocking an internal IP can break business processes and mask a compromised host that needs investigation, not just a firewall drop.
5. Monitor Fail2ban itself. Alert on: Fail2ban service failures (a dead Fail2ban is silent exposure), ban-volume spikes (may indicate a targeted campaign or a misconfigured threshold), and bans of internal/legitimate IPs (tuning signal). Log bans centrally so scan data feeds your SIEM.
6. Know the limits and layer up. Fail2ban sees only what the host's firewall logs: it misses slow scans below thresholds, distributed scans across many sources, and scans that don't hit logged rules. For serious environments, pair host-level Fail2ban with network IDS scan detection — Fail2ban is the bouncer, not the security architecture.

## Expected outputs

- Fail2ban scan-detection jails: filters, thresholds, and actions — tested with fail2ban-regex.
- Whitelist (ignoreip) with documented owners and review dates.
- Centralized ban logging feeding the SIEM.
- Monitoring for Fail2ban health and ban anomalies.

## Pitfalls

- Fail2ban only sees logged firewall traffic — scans against allowed ports or below thresholds are invisible.
- Overly aggressive thresholds block legitimate users (e.g., clients retrying a closed port) — tune from real data.
- Auto-blocking internal IPs can break business processes and hide compromised hosts — prefer alerting internally.
- IPv6 scanning needs separate log-pattern and jail consideration; many setups only cover IPv4.
- Fail2ban is reactive per-host blocking, not network scan intelligence — don't present it as IDS coverage.

## References

- Fail2ban manual (fail2ban.readthedocs.io): jails, filters, actions; MITRE ATT&CK T1595.002 (Active Scanning: Vulnerability Scanning) — https://attack.mitre.org/techniques/T1595/002/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
