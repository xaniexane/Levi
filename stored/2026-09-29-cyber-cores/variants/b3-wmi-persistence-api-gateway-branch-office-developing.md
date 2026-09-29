---
skill_id: cyber_b3_wmi_persistence_api_gateway_branch_office_developing
name: WMI Persistence Defense for API Gateways in Branch Offices (Developing Maturity)
description: "WMI Persistence defense playbook for API Gateways in Branch Offices at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, web, api, branch, network, maturity-developing]
version: 1.0.0
---
# WMI Persistence Defense for API Gateways in Branch Offices (Developing Maturity)

## Purpose

WMI event subscriptions trigger payloads on system events (timers, logons) with no visible scheduled task or service. They are fileless, stealthy, and missed by autorun tools that do not enumerate the WMI repository. Applies to API Gateways in Branch Offices at Developing maturity.

## When to use

- New __EventFilter/__EventConsumer/__FilterToConsumerBinding instances in the WMI repository, especially ActiveScript or CommandLine consumers with encoded commands.
- WmiPrvSE.exe spawning powershell/cmd at odd times, or WMI operational log entries for subscription creation.
- Persistence that survives task/service cleanup — the classic sign the mechanism is WMI-based.
- Lens: Best telemetry: per-request logs with API key/identity, endpoint, params hash, and response size. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Gateway access logs with authenticated identity per call; rate-limit trigger logs and Schema-validation failure logs (attacks often start as malformed requests); run `grep <api-key-id> /var/log/apigw/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -c 'schema_validation_failed' /var/log/apigw/error.log`.
3. **Analyze.** Enumerate all event subscriptions (Get-WMIObject -Namespace root\subscription) and inspect each consumer's command line. Then: Correlate subscription creation time with the initial compromise to confirm it is attacker-planted, not admin tooling.
4. **Contain and harden.** Alert on WMI subscription creation events; restrict WMI namespace permissions to administrators. Asset layer: Positive-security policies: schema validation, per-client rate limits, OAuth scopes per endpoint. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Declaring a host clean after checking tasks/services/registry but never looking at WMI subscriptions.
- Removing the consumer but leaving the filter and binding, which error silently and get recreated by the implant.

## References

- MITRE ATT&CK: T1047 (Execution: Windows Management Instrumentation)
- Vendor logging and hardening baselines for API Gateways; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
