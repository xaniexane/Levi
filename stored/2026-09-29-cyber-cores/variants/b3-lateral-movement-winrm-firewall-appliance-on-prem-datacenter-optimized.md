---
skill_id: cyber_b3_lateral_movement_winrm_firewall_appliance_on_prem_datacenter_optimized
name: WinRM Lateral Movement Defense for Firewall Appliances in On-Premises Datacenter (Optimized Maturity)
description: "WinRM Lateral Movement defense playbook for Firewall Appliances in On-Premises Datacenter at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, network, firewall, on-prem, datacenter, maturity-optimized]
version: 1.0.0
---
# WinRM Lateral Movement Defense for Firewall Appliances in On-Premises Datacenter (Optimized Maturity)

## Purpose

Windows Remote Management gives attackers remote PowerShell on any host where WinRM is enabled — quieter than PsExec, built into the OS, and often left on by default in enterprises. Applies to Firewall Appliances in On-Premises Datacenter at Optimized maturity.

## When to use

- WinRM operational log (Microsoft-Windows-WinRM/Operational) showing connections from non-admin workstations, or wsmprovhost spawning powershell with encoded commands.
- Event 4624 type-3 logons to the WinRM port (5985/5986) from hosts outside the management subnet.
- PowerShell remoting sessions (event 400/800) executing reconnaissance or credential-access commands.
- Lens: Best telemetry: traffic/deny logs + admin audit log + config-change diffs shipped to SIEM. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Traffic logs (allowed/denied with rule IDs), threat logs (IPS/AV verdicts), admin audit log and Configuration revisions and diffs; VPN session logs and authentication failures; run `# vendor CLIs differ; conceptually:` then `show log traffic query (source <suspect-ip>)             # Palo Alto style`.
3. **Analyze.** Extract the remote commands from PowerShell operational logs (4104) on the target to see exactly what the attacker ran. Then: Inventory which hosts have WinRM enabled and reachable — the attack surface is every one of them.
4. **Contain and harden.** Restrict WinRM to management hosts via host firewall and GPO; disable where not needed. Asset layer: Default-deny with documented rules, admin on dedicated interface with MFA, config backups versioned. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Forgetting WinRM over HTTPS (5986) when firewalling only 5985.
- PowerShell logging gaps: without module/script-block logging, remote commands are invisible — enable both.

## References

- MITRE ATT&CK: T1021.006 (Lateral Movement: Windows Remote Management)
- Vendor logging and hardening baselines for Firewall Appliances; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
