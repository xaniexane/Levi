---
skill_id: cyber_b3_service_persistence_linux_server_remote_workforce_defined
name: Malicious Service Persistence Defense for Linux Servers in Remote Workforce (Defined Maturity)
description: "Malicious Service Persistence defense playbook for Linux Servers in Remote Workforce at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, linux, server, remote, endpoint, zero-trust, maturity-defined]
version: 1.0.0
---
# Malicious Service Persistence Defense for Linux Servers in Remote Workforce (Defined Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to Linux Servers in Remote Workforce at Defined maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for Linux Servers; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
