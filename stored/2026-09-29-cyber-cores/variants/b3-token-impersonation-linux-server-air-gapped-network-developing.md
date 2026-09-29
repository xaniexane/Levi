---
skill_id: cyber_b3_token_impersonation_linux_server_air_gapped_network_developing
name: Token Impersonation Defense for Linux Servers in Air-Gapped Networks (Developing Maturity)
description: "Token Impersonation defense playbook for Linux Servers in Air-Gapped Networks at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, linux, server, air-gap, ot, high-security, maturity-developing]
version: 1.0.0
---
# Token Impersonation Defense for Linux Servers in Air-Gapped Networks (Developing Maturity)

## Purpose

Attackers steal or duplicate Windows access tokens to act as another user — often SYSTEM — without knowing any password. EDR sees odd parent/child relationships and token-privilege enabling that legitimate software rarely performs. Applies to Linux Servers in Air-Gapped Networks at Developing maturity.

## When to use

- Processes enabling SeDebugPrivilege or SeImpersonatePrivilege outside of known admin tooling, or unexpected token duplication API sequences in EDR telemetry.
- A low-privilege process spawning children as SYSTEM or as another logged-on user without a legitimate service path.
- Named-pipe impersonation patterns (PrintSpooler-style) from non-printer processes.
- Lens: Best telemetry: auditd + centralized syslog/journald + osquery or an EDR agent. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in auth.log/secure (SSH logons), auditd logs (execve, file writes), and cron tables (/etc/crontab, /etc/cron.d/*, user crontabs) and systemd unit files in /etc/systemd/system/ and SSH authorized_keys files for all users; run `sudo grep -E 'Failed|Accepted' /var/log/auth.log | tail -40` then `sudo ausearch -m EXECVE --start recent -i | grep -E 'curl|wget|bash|sh|python|perl' | tail -30`.
3. **Analyze.** Trace the token source: which process's token was stolen, and did that source process itself get compromised first? Then: Check what the impersonated context accessed — file, registry, and network actions taken as the victim identity.
4. **Contain and harden.** Remove SeImpersonatePrivilege from service accounts that do not need it; patch print-spooler-class vulnerabilities promptly. Asset layer: Key-only SSH (no passwords), fail2ban or equivalent, unattended security updates enabled. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming token theft requires admin — some impersonation primitives work from lower privilege.
- Missing that a stolen token can be replayed on OTHER hosts via remote authentication.

## References

- MITRE ATT&CK: T1134 (Privilege Escalation: Access Token Manipulation)
- Vendor logging and hardening baselines for Linux Servers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
