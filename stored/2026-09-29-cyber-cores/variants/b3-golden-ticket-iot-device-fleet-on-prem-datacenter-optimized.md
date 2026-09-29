---
skill_id: cyber_b3_golden_ticket_iot_device_fleet_on_prem_datacenter_optimized
name: Golden Ticket Attack Defense for IoT Device Fleets in On-Premises Datacenter (Optimized Maturity)
description: "Golden Ticket Attack defense playbook for IoT Device Fleets in On-Premises Datacenter at Optimized maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [identity, active-directory, iot, network, on-prem, datacenter, maturity-optimized]
version: 1.0.0
---
# Golden Ticket Attack Defense for IoT Device Fleets in On-Premises Datacenter (Optimized Maturity)

## Purpose

Forged Kerberos TGTs using the stolen krbtgt hash grant unrestricted, long-lived domain access that survives password resets. Detection relies on ticket anomalies: impossible lifetimes, wrong encryption, or logons that bypass the DC. Applies to IoT Device Fleets in On-Premises Datacenter at Optimized maturity.

## When to use

- TGTs with lifetimes far exceeding domain policy (e.g., 10 years), RC4-encrypted tickets in an AES-enforced domain, or tickets for accounts that never authenticated (no 4768).
- 4769 service-ticket requests referencing a TGT the DC never issued, or logons from hosts with no corresponding interactive session.
- The krbtgt account's own anomalous activity following a DCSync event.
- Lens: Best telemetry: device heartbeat/status + firmware version inventory + network flow from IoT VLAN. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Device inventory with firmware versions and last-seen timestamps and Network flows from the IoT segment (unexpected destinations, scanning behavior); run `nmap -sn 192.0.2.0/24 2>/dev/null | grep -E 'Nmap scan|MAC' | head -40   # authorized scan only` then `grep <device-ip> /var/log/iot-flows.log | awk '{print $5}' | sort | uniq -c | sort -rn | head -15`.
3. **Analyze.** Confirm via ticket inspection (klist, network capture): lifetime, encryption type, and client name mismatches prove forgery. Then: Scope everything done under forged tickets — assume full domain compromise until proven otherwise.
4. **Contain and harden.** Rotate the krbtgt password TWICE (to invalidate both current and previous hash) after any suspected compromise. Asset layer: Dedicated VLAN with no internet egress except via proxy, unique credentials per device, firmware update process. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating krbtgt only once — the N-1 hash remains valid and the golden ticket still works.
- Treating it as an account incident instead of a domain-trust incident; the response scope is the whole forest.

## References

- MITRE ATT&CK: T1558.001 (Credential Access: Golden Ticket)
- Vendor logging and hardening baselines for IoT Device Fleets; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
