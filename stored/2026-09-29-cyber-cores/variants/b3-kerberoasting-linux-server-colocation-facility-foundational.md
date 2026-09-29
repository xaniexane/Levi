---
skill_id: cyber_b3_kerberoasting_linux_server_colocation_facility_foundational
name: Kerberoasting Defense for Linux Servers in Colocation Facilities (Foundational Maturity)
description: "Kerberoasting defense playbook for Linux Servers in Colocation Facilities at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, linux, server, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Kerberoasting Defense for Linux Servers in Colocation Facilities (Foundational Maturity)

## Purpose

Attackers request service tickets for SPN accounts and crack them offline to recover service-account passwords — no alerts on the DC, because requesting tickets is normal. The defense is making those passwords uncrackable and the requests visible. Applies to Linux Servers in Colocation Facilities at Foundational maturity.

## When to use

- A single account requesting an unusual number of service tickets (4769) with RC4 encryption for many different SPNs in a short window.
- Ticket requests for SPNs from accounts with no business need, or requests at odd hours from a workstation (not a server).
- Subsequent use of a cracked service account: logons from unexpected hosts or privilege changes for that account.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** List every SPN targeted and assess the crackability of each service account's password (length, complexity, age). Then: If a service account was cracked, treat it as full compromise: inventory everything that account could touch.
4. **Contain and harden.** Service accounts: 25+ character random passwords, or better, group Managed Service Accounts (gMSA) with automatic rotation. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the password but leaving the SPN on a weak account — the attacker just roasts it again.
- Missing that the cracked service account may have been used to request MORE tickets (roast chaining).

## References

- MITRE ATT&CK: T1558.003 (Credential Access: Kerberoasting)
- Vendor logging and hardening baselines for Linux Servers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
