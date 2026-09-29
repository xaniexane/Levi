---
skill_id: cyber_b3_privilege_escalation_windows_linux_server_colocation_facility_optimized
name: Windows Privilege Escalation Defense for Linux Servers in Colocation Facilities (Optimized Maturity)
description: "Windows Privilege Escalation defense playbook for Linux Servers in Colocation Facilities at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, linux, server, on-prem, colocation, maturity-optimized]
version: 1.0.0
---
# Windows Privilege Escalation Defense for Linux Servers in Colocation Facilities (Optimized Maturity)

## Purpose

From standard user to SYSTEM/Administrator via unquoted service paths, writable service binaries, AlwaysInstallElevated, token manipulation, or kernel exploits. Windows privesc is usually a misconfiguration the attacker read, not a zero-day they brought. Applies to Linux Servers in Colocation Facilities at Optimized maturity.

## When to use

- Service creation or modification events (7045/4697) pointing at user-writable paths, or processes spawning as SYSTEM from unexpected parents.
- Registry writes to AlwaysInstallElevated keys, accessibility binary replacement (sethc/utilman), or token duplication API patterns in EDR telemetry.
- Enumeration tooling: whoami /priv, accesschk, or PowerShell privesc scripts running before the escalation.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** Pin down the primitive: unquoted path, weak service ACL, scheduled task with stored creds, or kernel CVE — then check how many fleet hosts share it. Then: Review what the elevated access touched: SAM/LSASS access after escalation means credential theft followed.
4. **Contain and harden.** Fix service ACLs and paths fleet-wide, disable AlwaysInstallElevated, and enforce signed-driver and LSA protection policies. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Reimaging one host while the GPO-deployed misconfiguration recreates the hole on every rebuild.
- Missing that the attacker already dumped credentials post-escalation — scope the follow-on theft, not just the privesc.

## References

- MITRE ATT&CK: T1068 (Privilege Escalation: Exploitation for Privilege Escalation)
- Vendor logging and hardening baselines for Linux Servers; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
