---
skill_id: cyber_detecting_lateral_movement_in_network
name: Detecting Lateral Movement in the Network
description: General methodology for detecting adversary lateral movement across enterprise networks.
risk: low
permissions: []
requires_confirmation: false
tags: [lateral-movement, network, detection]
version: 1.0.0
---
## Purpose

Lateral movement — an attacker expanding from one compromised host to others — is where breaches turn from incidents into disasters. This playbook gives defenders a general detection methodology: what telemetry to collect, which movement patterns matter, and how to distinguish attacker pivoting from normal administrative traffic.

## When to use

- You need a lateral-movement detection strategy from scratch.
- An incident responder asks 'are they anywhere else?' and you need a systematic answer.
- EDR coverage is partial and you must rely on network and authentication logs.
- Tuning existing rules that fire constantly on admin activity.

## Prerequisites

- Centralized authentication logs: Windows Security events (4624/4625 logons, 4672 special privileges), VPN/IdP logs, and Linux auth logs (sshd).
- Network flow data (NetFlow/IPFIX) or firewall logs between internal segments.
- An asset inventory distinguishing servers, workstations, admin jump hosts, and service accounts.
- Known-good baselines of administrative tooling: who uses RDP/SSH/WinRM/PSExec legitimately, from where, to where.

## Procedure

1. Map your authentication telemetry. Ensure logon events include logon type (2 interactive, 3 network, 10 RDP), source IP/hostname, account, and target host. Lateral movement most often appears as Type 3/10 logons with mismatched expectations.
2. Build allowlists of normal admin paths. Document legitimate lateral patterns: helpdesk RDP to workstations, deployment tools pushing to servers, backup service accounts. Detection works by exception — you cannot find abnormal until normal is defined.
3. Hunt for the classic movement indicators: a workstation initiating SMB/RDP/WinRM to many hosts (fan-out); logons using local administrator or shared credentials across multiple machines; first-time host-to-host connections between systems that never talk; authentication with privileged accounts from non-admin workstations; and logon sessions at unusual hours.
4. Correlate with endpoint data where available. A network logon followed by process creation of reconnaissance commands (network discovery, credential access) on the target within minutes is high-confidence movement. Single telemetry sources lie; correlated ones rarely do.
5. Scope aggressively once movement is confirmed. For each compromised host, list every outbound authentication and every inbound session in the window, then repeat for each newly discovered host. Attackers move in chains — one hop of scoping is never enough.
6. Contain by account and path, not just host. Reset credentials for accounts used in movement, block the abused protocols at segment boundaries where business allows, and isolate hosts. Remember: re-imaging a host without resetting the credentials the attacker harvested just gives them a fresh target.

## Expected outputs

- Documented normal-admin-path allowlist and lateral-movement detection rules with tuning notes.
- Scoping worksheet template: per-host inbound/outbound authentication mapping.
- Confirmed-movement response checklist: isolation, credential reset, protocol blocks.
- Metrics: mean time to detect movement, scoped host count per incident, false-positive rate.

## Pitfalls

- Alerting on every RDP session without an admin-path allowlist buries analysts — baseline first.
- Service accounts and scanners (vulnerability scanners, asset discovery) look exactly like lateral movement; inventory them or they become permanent false positives.
- Encrypted protocols (RDP, SSH) hide payload but not metadata — don't discard flow/auth logs because you can't see content.
- Stopping at the first compromised host misses the chain; scope iteratively until no new hosts appear.
- DHCP/NAT can make 'source host' attribution wrong — correlate with EDR hostname or DHCP logs before accusing a machine.

## References

- MITRE ATT&CK Lateral Movement tactics (TA0008) — https://attack.mitre.org/tactics/TA0008/; NIST SP 800-92 (log management); SANS guidance on Windows logon types and lateral movement detection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
