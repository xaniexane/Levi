---
skill_id: cyber_b3_lateral_movement_winrm_iot_device_fleet_azure_cloud_managed
name: WinRM Lateral Movement Defense for IoT Device Fleets in Azure Cloud (Managed Maturity)
description: "WinRM Lateral Movement defense playbook for IoT Device Fleets in Azure Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, lateral-movement, iot, network, cloud, azure, maturity-managed]
version: 1.0.0
---
# WinRM Lateral Movement Defense for IoT Device Fleets in Azure Cloud (Managed Maturity)

## Purpose

Windows Remote Management gives attackers remote PowerShell on any host where WinRM is enabled — quieter than PsExec, built into the OS, and often left on by default in enterprises. Applies to IoT Device Fleets in Azure Cloud at Managed maturity.

## When to use

- WinRM operational log (Microsoft-Windows-WinRM/Operational) showing connections from non-admin workstations, or wsmprovhost spawning powershell with encoded commands.
- Event 4624 type-3 logons to the WinRM port (5985/5986) from hosts outside the management subnet.
- PowerShell remoting sessions (event 400/800) executing reconnaissance or credential-access commands.
- Lens: Best telemetry: device heartbeat/status + firmware version inventory + network flow from IoT VLAN. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Device inventory with firmware versions and last-seen timestamps and Network flows from the IoT segment (unexpected destinations, scanning behavior); run `nmap -sn 192.0.2.0/24 2>/dev/null | grep -E 'Nmap scan|MAC' | head -40   # authorized scan only` then `grep <device-ip> /var/log/iot-flows.log | awk '{print $5}' | sort | uniq -c | sort -rn | head -15`.
3. **Analyze.** Extract the remote commands from PowerShell operational logs (4104) on the target to see exactly what the attacker ran. Then: Inventory which hosts have WinRM enabled and reachable — the attack surface is every one of them.
4. **Contain and harden.** Restrict WinRM to management hosts via host firewall and GPO; disable where not needed. Asset layer: Dedicated VLAN with no internet egress except via proxy, unique credentials per device, firmware update process. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Forgetting WinRM over HTTPS (5986) when firewalling only 5985.
- PowerShell logging gaps: without module/script-block logging, remote commands are invisible — enable both.

## References

- MITRE ATT&CK: T1021.006 (Lateral Movement: Windows Remote Management)
- Vendor logging and hardening baselines for IoT Device Fleets; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
