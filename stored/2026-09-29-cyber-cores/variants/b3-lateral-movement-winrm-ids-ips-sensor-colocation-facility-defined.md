---
skill_id: cyber_b3_lateral_movement_winrm_ids_ips_sensor_colocation_facility_defined
name: WinRM Lateral Movement Defense for IDS/IPS Sensors in Colocation Facilities (Defined Maturity)
description: "WinRM Lateral Movement defense playbook for IDS/IPS Sensors in Colocation Facilities at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, network, ids, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# WinRM Lateral Movement Defense for IDS/IPS Sensors in Colocation Facilities (Defined Maturity)

## Purpose

Windows Remote Management gives attackers remote PowerShell on any host where WinRM is enabled — quieter than PsExec, built into the OS, and often left on by default in enterprises. Applies to IDS/IPS Sensors in Colocation Facilities at Defined maturity.

## When to use

- WinRM operational log (Microsoft-Windows-WinRM/Operational) showing connections from non-admin workstations, or wsmprovhost spawning powershell with encoded commands.
- Event 4624 type-3 logons to the WinRM port (5985/5986) from hosts outside the management subnet.
- PowerShell remoting sessions (event 400/800) executing reconnaissance or credential-access commands.
- Lens: Best telemetry: alert logs with full packet captures for high-severity events + sensor health metrics. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Signature alert logs with triggering packet payloads; anomaly-detection baselines and deviations and PCAP ring buffers for incident windows; sensor placement/coverage maps; run `# Suricata/Snort style triage:` then `jq -c 'select(.alert.severity<=2) | {ts:.timestamp, sig:.alert.signature, src:.src_ip, dst:.dest_ip}' /var/log/suricata/eve.json | tail -20`.
3. **Analyze.** Extract the remote commands from PowerShell operational logs (4104) on the target to see exactly what the attacker ran. Then: Inventory which hosts have WinRM enabled and reachable — the attack surface is every one of them.
4. **Contain and harden.** Restrict WinRM to management hosts via host firewall and GPO; disable where not needed. Asset layer: Sensors on SPAN/TAP at every trust boundary; signature sets auto-updated; TLS inspection feeding sensors. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Forgetting WinRM over HTTPS (5986) when firewalling only 5985.
- PowerShell logging gaps: without module/script-block logging, remote commands are invisible — enable both.

## References

- MITRE ATT&CK: T1021.006 (Lateral Movement: Windows Remote Management)
- Vendor logging and hardening baselines for IDS/IPS Sensors; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
