---
skill_id: cyber_b3_privilege_escalation_sudo_linux_workstation_branch_office_managed
name: Linux Privilege Escalation Defense for Linux Workstations in Branch Offices (Managed Maturity)
description: "Linux Privilege Escalation defense playbook for Linux Workstations in Branch Offices at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privilege-escalation, endpoint, branch, network, maturity-managed]
version: 1.0.0
---
# Linux Privilege Escalation Defense for Linux Workstations in Branch Offices (Managed Maturity)

## Purpose

Attackers turn a low-privilege Linux foothold into root via sudo misconfigurations, SUID binaries, kernel exploits, or writable service files. Harden the escalation paths and you contain most Linux intrusions at the beachhead. Applies to Linux Workstations in Branch Offices at Managed maturity.

## When to use

- Sudo invocations of unusual binaries, sudoers file reads by non-admins, or successful sudo from accounts that never used it before.
- Execution of known privesc enumeration scripts (LinPEAS-style), SUID binary abuse, or kernel exploit artifacts in logs.
- New entries in sudoers.d, unexpected SUID bits, or service files modified by non-root users.
- Lens: Best telemetry: auditd user-session logging + EDR agent + desktop shell histories (with user notice). SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in User shell histories (~/.bash_history), desktop autostart entries (~/.config/autostart/) and auditd execve logs and USB device logs; browser profiles for web-vector cases; run `ls -la ~/.config/autostart/ 2>/dev/null; grep -r 'Exec=' ~/.config/autostart/ 2>/dev/null` then `sudo ausearch --start recent -m EXECVE -i | tail -30`.
3. **Analyze.** Identify the exact escalation primitive: which misconfiguration or vulnerability was used, and whether it is systemic across the fleet or host-specific. Then: Check for persistence installed with the new privileges: new SSH keys in root's authorized_keys, cron jobs, or systemd units.
4. **Contain and harden.** Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID from unnecessary binaries, and keep kernels patched. Asset layer: Standard user accounts for daily work, full-disk encryption, and screen-lock enforcement. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the host without fixing the fleet-wide sudoers misconfiguration that enabled it.
- Assuming container escape is out of scope — check whether the foothold was a container with host mounts.

## References

- MITRE ATT&CK: T1548.003 (Privilege Escalation: Sudo and Sudo Caching)
- Vendor logging and hardening baselines for Linux Workstations; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
