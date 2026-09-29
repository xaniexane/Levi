---
skill_id: cyber_b3_lateral_movement_winrm_edr_console_air_gapped_network_foundational
name: WinRM Lateral Movement Defense for EDR Consoles in Air-Gapped Networks (Foundational Maturity)
description: "WinRM Lateral Movement defense playbook for EDR Consoles in Air-Gapped Networks at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, soc, edr, endpoint, air-gap, ot, high-security, maturity-foundational]
version: 1.0.0
---
# WinRM Lateral Movement Defense for EDR Consoles in Air-Gapped Networks (Foundational Maturity)

## Purpose

Windows Remote Management gives attackers remote PowerShell on any host where WinRM is enabled — quieter than PsExec, built into the OS, and often left on by default in enterprises. Applies to EDR Consoles in Air-Gapped Networks at Foundational maturity.

## When to use

- WinRM operational log (Microsoft-Windows-WinRM/Operational) showing connections from non-admin workstations, or wsmprovhost spawning powershell with encoded commands.
- Event 4624 type-3 logons to the WinRM port (5985/5986) from hosts outside the management subnet.
- PowerShell remoting sessions (event 400/800) executing reconnaissance or credential-access commands.
- Lens: Best telemetry: raw process/network telemetry + detection history + sensor health inventory. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Full process trees with command lines, hashes, and network connections for suspect hosts and Detection and response action history (isolations, kills, quarantines); run `# conceptually (EDR APIs differ):` then `edr-cli hunt process --hostname <host> --since 24h --tree`.
3. **Analyze.** Extract the remote commands from PowerShell operational logs (4104) on the target to see exactly what the attacker ran. Then: Inventory which hosts have WinRM enabled and reachable — the attack surface is every one of them.
4. **Contain and harden.** Restrict WinRM to management hosts via host firewall and GPO; disable where not needed. Asset layer: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Forgetting WinRM over HTTPS (5986) when firewalling only 5985.
- PowerShell logging gaps: without module/script-block logging, remote commands are invisible — enable both.

## References

- MITRE ATT&CK: T1021.006 (Lateral Movement: Windows Remote Management)
- Vendor logging and hardening baselines for EDR Consoles; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
