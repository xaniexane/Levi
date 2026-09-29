---
skill_id: cyber_b3_privilege_escalation_sudo_macos_endpoint_hybrid_cloud_foundational
name: Linux Privilege Escalation Defense for macOS Endpoints in Hybrid Cloud (Foundational Maturity)
description: "Linux Privilege Escalation defense playbook for macOS Endpoints in Hybrid Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [linux, privilege-escalation, macos, endpoint, hybrid, cloud, on-prem, maturity-foundational]
version: 1.0.0
---
# Linux Privilege Escalation Defense for macOS Endpoints in Hybrid Cloud (Foundational Maturity)

## Purpose

Attackers turn a low-privilege Linux foothold into root via sudo misconfigurations, SUID binaries, kernel exploits, or writable service files. Harden the escalation paths and you contain most Linux intrusions at the beachhead. Applies to macOS Endpoints in Hybrid Cloud at Foundational maturity.

## When to use

- Sudo invocations of unusual binaries, sudoers file reads by non-admins, or successful sudo from accounts that never used it before.
- Execution of known privesc enumeration scripts (LinPEAS-style), SUID binary abuse, or kernel exploit artifacts in logs.
- New entries in sudoers.d, unexpected SUID bits, or service files modified by non-root users.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. Unified SIEM ingesting both on-prem syslog and cloud audit trails with identity correlation across both.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Conditional-access and network logs covering the interconnect (ExpressRoute/Direct Connect/VPN).

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Identify the exact escalation primitive: which misconfiguration or vulnerability was used, and whether it is systemic across the fleet or host-specific. Then: Check for persistence installed with the new privileges: new SSH keys in root's authorized_keys, cron jobs, or systemd units.
4. **Contain and harden.** Least-privilege sudoers (no NOPASSWD, no wildcards), remove SUID from unnecessary binaries, and keep kernels patched. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the host without fixing the fleet-wide sudoers misconfiguration that enabled it.
- Assuming container escape is out of scope — check whether the foothold was a container with host mounts.

## References

- MITRE ATT&CK: T1548.003 (Privilege Escalation: Sudo and Sudo Caching)
- Vendor logging and hardening baselines for macOS Endpoints; Consistent identity (single IdP) across on-prem and cloud; no parallel credential stores.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
