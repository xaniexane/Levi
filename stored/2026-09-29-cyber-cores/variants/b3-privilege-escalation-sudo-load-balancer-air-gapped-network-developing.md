---
skill_id: cyber_b3_privilege_escalation_sudo_load_balancer_air_gapped_network_developing
name: Linux Privilege Escalation Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)
description: "Linux Privilege Escalation defense playbook for Load Balancers in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privilege-escalation, network, web, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Linux Privilege Escalation Defense for Load Balancers in Air-Gapped Networks (Developing Maturity)

## Purpose

Attackers turn a low-privilege Linux foothold into root via sudo misconfigurations, SUID binaries, kernel exploits, or writable service files. Harden the escalation paths and you contain most Linux intrusions at the beachhead. Applies to Load Balancers in Air-Gapped Networks at Developing maturity.

## When to use

- Sudo invocations of unusual binaries, sudoers file reads by non-admins, or successful sudo from accounts that never used it before.
- Execution of known privesc enumeration scripts (LinPEAS-style), SUID binary abuse, or kernel exploit artifacts in logs.
- New entries in sudoers.d, unexpected SUID bits, or service files modified by non-root users.
- Lens: Best telemetry: access logs with X-Forwarded-For + backend health flaps + config-change audit. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (client IP, Host header, URI, status, bytes) — the edge view of web attacks and Backend pool changes and health-check failure histories; run `grep -E ' 4[0-9]{2} ' /var/log/haproxy.log | awk '{print $6}' | sort | uniq -c | sort -rn | head -15` then `echo 'show stat' | socat unix-connect:/var/run/haproxy.sock stdio 2>/dev/null | cut -d, -f1,2,18 | head -20`.
3. **Analyze.** Identify the exact escalation primitive: which misconfiguration or vulnerability was used, and whether it is systemic across the fleet or host-specific. Then: Check for persistence installed with the new privileges: new SSH keys in root's authorized_keys, cron jobs, or systemd units.
4. **Contain and harden.** Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID from unnecessary binaries, and keep kernels patched. Asset layer: TLS 1.2+ with strong ciphers, HSTS, WAF integration at the edge, config changes via version control. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the host without fixing the fleet-wide sudoers misconfiguration that enabled it.
- Assuming container escape is out of scope — check whether the foothold was a container with host mounts.

## References

- MITRE ATT&CK: T1548.003 (Privilege Escalation: Sudo and Sudo Caching)
- Vendor logging and hardening baselines for Load Balancers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
