---
skill_id: cyber_b3_c2_beaconing_wifi_controller_air_gapped_network_managed
name: C2 Beaconing Defense for Wireless Controllers in Air-Gapped Networks (Managed Maturity)
description: "C2 Beaconing defense playbook for Wireless Controllers in Air-Gapped Networks at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, c2, wireless, air-gap, ot, high-security, maturity-managed]
version: 1.0.0
---
# C2 Beaconing Defense for Wireless Controllers in Air-Gapped Networks (Managed Maturity)

## Purpose

Compromised hosts check in with attacker infrastructure on a schedule — the heartbeat of an intrusion. Beaconing detection is statistical: regularity, jitter analysis, and connection uniformity reveal what signatures miss. Applies to Wireless Controllers in Air-Gapped Networks at Managed maturity.

## When to use

- Outbound connections at fixed intervals (e.g., every 60s) with consistent byte counts to an external host — visible in NetFlow or proxy logs as metronomic traffic.
- Long-lived sessions to IPs with no domain, newly registered domains, or domains with no legitimate business purpose.
- Jittered but statistically regular timing: inter-arrival times clustering around a mean with small variance.
- Lens: Best telemetry: client association/auth logs + rogue-AP detection + RADIUS accounting. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Client association, authentication (EAP) and roaming logs with device MACs and Rogue AP / evil-twin detections and deauth-flood alerts from WIDS; run `# conceptually (vendor CLIs differ):` then `show wireless client summary | include <suspect-mac>`.
3. **Analyze.** Compute inter-arrival statistics on the suspect flows; true beacons show low variance even with jitter, unlike human browsing. Then: Capture the beacon payload in a sandbox detonation to identify the implant family and its tasking protocol.
4. **Contain and harden.** Egress filtering: default-deny outbound with allowlisted destinations for servers; alert on direct-to-IP connections. Asset layer: WPA3-Enterprise with EAP-TLS (certificates, not PSK); rogue-AP containment enabled. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Chasing the C2 IP instead of the implant — infrastructure is disposable, the foothold is what matters.
- Assuming encrypted traffic cannot be analyzed: timing, size, and destination metadata still betray beacons.

## References

- MITRE ATT&CK: T1071.001 (Command and Control: Web Protocols)
- Vendor logging and hardening baselines for Wireless Controllers; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
