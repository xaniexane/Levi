---
skill_id: cyber_detecting_rdp_brute_force_attacks
name: Detecting RDP Brute Force Attacks
description: Detect and respond to RDP brute-force and password-spraying attacks.
risk: low
permissions: []
requires_confirmation: false
tags: [rdp, brute-force, detection]
version: 1.0.0
---
## Purpose

Exposed RDP remains one of the most attacked services on the internet — brute-force and password-spraying campaigns run constantly, and a single success often leads directly to ransomware. This playbook covers detecting RDP brute-force from Windows logs and network telemetry, responding to successes, and reducing the RDP attack surface.

## When to use

- RDP is exposed (directly or via VPN) and you need brute-force detection.
- Event logs show 4625 spikes against RDP and you need a triage procedure.
- A successful RDP brute-force is suspected — scope and respond.
- Compliance requires monitoring of remote-access authentication.

## Prerequisites

- Windows Security logs from RDP-exposed hosts: Event IDs 4625 (failed logon), 4624 (successful logon, Type 10 for RDP), 4776/4768/4771 for credential validation.
- Network/firewall logs showing inbound RDP connection attempts per source.
- Inventory of where RDP is legitimately exposed and to whom.
- Account lockout policy and baseline failed-logon rates.

## Procedure

1. Detect the brute-force pattern. Alert on: high 4625 rates per source IP (classic brute force), low-and-slow 4625 spread across many usernames from one source (password spraying), 4625 bursts against privileged accounts (Administrator), and RDP connection attempts from geographies with no business presence. Distinguish spraying (many users, few passwords) from brute force (one user, many passwords) — the response differs.
2. Detect the success that matters. The critical alert is 4625 failure bursts followed by a 4624 Type 10 success for the same account — especially from an external IP, at an unusual hour, or for an account that never uses RDP. Any external RDP success following failures is a compromise until proven otherwise; also alert on first-time external RDP success per account regardless of preceding failures.
3. Triage with context. For each alert determine: source IP reputation and history, targeted accounts (service accounts brute-forced suggest automated tooling; executives suggest targeting), whether MFA/conditional access applied, and whether the source also probed other services (campaign indicator). Check for concurrent successful logons to other systems from the same source.
4. Respond to successful brute-force as an intrusion. Isolate the host, force password reset and session revocation for the compromised account, review the account's activity window (what did the attacker access?), hunt for persistence (new accounts, scheduled tasks, RDP wrapper modifications), and check for lateral movement from the host. Assume the full session was malicious.
5. Reduce the RDP surface structurally: remove direct internet exposure (VPN/ZTNA/RD Gateway with MFA), enforce account lockout and strong passwords, rename/disable default Administrator, restrict RDP via host firewall to known ranges, deploy RDP-specific IDS rules, and consider honeypot RDP listeners for early warning. Detection is necessary; exposure removal is the fix.

## Expected outputs

- RDP brute-force/spray detections: per-source failure rates, spray patterns, privileged-account targeting.
- Success-after-failure correlation alert with compromise-response trigger.
- Triage checklist: source intel, targeted accounts, MFA status, campaign context.
- RDP exposure inventory and reduction plan (gateway, MFA, firewall restrictions).

## Pitfalls

- Account lockout policies can be weaponized for denial of service — pair with IP-based blocking, not lockout alone.
- Password spraying stays under per-account lockout thresholds by design — detect across accounts per source.
- Legitimate users fat-fingering passwords generate 4625s; require rate/pattern thresholds, not single failures.
- VPN-concentrated RDP hides source IPs — ensure pre-VPN or gateway logs preserve origin.
- Blocking the IP without investigating the success case misses the breach — success alerts always outrank block stats.

## References

- MITRE ATT&CK T1110 (Brute Force), T1133 (External Remote Services) — https://attack.mitre.org/techniques/T1110/; Microsoft Learn: RDP security best practices; CISA guidance on reducing RDP exposure
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
