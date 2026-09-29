---
skill_id: cyber_b3_wmi_persistence_edr_console_branch_office_optimized
name: WMI Persistence Defense for EDR Consoles in Branch Offices (Optimized Maturity)
description: "WMI Persistence defense playbook for EDR Consoles in Branch Offices at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, soc, edr, endpoint, branch, network, maturity-optimized]
version: 1.0.0
---
# WMI Persistence Defense for EDR Consoles in Branch Offices (Optimized Maturity)

## Purpose

WMI event subscriptions trigger payloads on system events (timers, logons) with no visible scheduled task or service. They are fileless, stealthy, and missed by autorun tools that do not enumerate the WMI repository. Applies to EDR Consoles in Branch Offices at Optimized maturity.

## When to use

- New __EventFilter/__EventConsumer/__FilterToConsumerBinding instances in the WMI repository, especially ActiveScript or CommandLine consumers with encoded commands.
- WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI operational log entries for subscription creation.
- Persistence that survives task/service cleanup — the classic sign the mechanism is WMI-based.
- Lens: Best telemetry: raw process/network telemetry + detection history + sensor health inventory. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Full process trees with command lines, hashes, and network connections for suspect hosts and Detection and response action history (isolations, kills, quarantines); run `# conceptually (EDR APIs differ):` then `edr-cli hunt process --hostname <host> --since 24h --tree`.
3. **Analyze.** Enumerate all event subscriptions (Get-WMIObject -Namespace root\subscription) and inspect each consumer's command line. Then: Correlate subscription creation time with the initial compromise to confirm it is attacker-planted, not admin tooling.
4. **Contain and harden.** Alert on WMI subscription creation events; restrict WMI namespace permissions to administrators. Asset layer: Tamper protection locked with console-only disable, auto-isolation policies for high-severity detections. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring a host clean after checking tasks/services/registry but never looking at WMI subscriptions.
- Removing the consumer but leaving the filter and binding, which error silently and get recreated by the implant.

## References

- MITRE ATT&CK: T1047 (Execution: Windows Management Instrumentation)
- Vendor logging and hardening baselines for EDR Consoles; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
