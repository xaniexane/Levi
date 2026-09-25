---
skill_id: cyber_detecting_attacks_on_historian_servers
name: Detecting Attacks on Historian Servers
description: Detect compromise of OT historian servers with integrity monitoring, access baselining, and boundary alerting.
risk: info
permissions: []
requires_confirmation: false
tags: [ics, ot, detection]
version: 1.0.0
---
## Purpose

Protect the historian — the OT data repository that attackers target for process intelligence, manipulation, and as a pivot between IT and OT. Detect unauthorized access, data tampering, and misuse of historian interfaces with monitoring that respects OT safety constraints.

## When to use

- Hardening OT data infrastructure (OSIsoft PI / AVEVA PI, Wonderware, GE Proficy historians).
- Investigating suspected process-data manipulation or industrial espionage.
- Validating the IT/OT boundary where the historian is the primary conduit.
- Post-incident scoping when an attacker may have harvested process intelligence.

## Prerequisites

- Operations/engineering partnership — historian changes affect production data flows.
- Inventory: historian version, interfaces (OPC, APIs, web clients), replication partners, and authorized client hosts.
- Passive network visibility on historian segments; host-level audit capability on the historian server.
- Baseline of normal historian access patterns: which systems replicate, which users query, normal data volumes.

## Procedure

1. **Baseline legitimate historian interactions.** Document: replication flows (which historians sync, on what schedule), OPC client connections (which HMIs/applications, which tags), web/API query patterns, and administrative access (who manages the historian, from where). The historian's traffic is highly regular — deviations are meaningful.
2. **Monitor authentication and access to the historian.** Alert on: logons from unauthorized hosts, new user accounts or permission changes on the historian, access outside maintenance windows, and bulk tag/data exports (an attacker mapping the process exports everything; engineers query selectively).
3. **Detect data-integrity attacks.** Alert on: historical data modifications (backfilled or altered values — historians normally append), tag configuration changes (renames, deletions, new tags), and gaps or anomalies in data collection that suggest suppression. Compare historian data against independent process sources where available.
4. **Watch the historian's interfaces as attack surface.** Monitor the OPC interfaces, web clients, and APIs for: vulnerability-exploitation patterns, authentication bypass attempts, and unusual query structures. Keep the historian patched per the vendor's OT-safe guidance and track CVEs against your exact version.
5. **Guard the replication and boundary paths.** The historian often bridges IT and OT. Alert on: new replication partners, replication to unexpected destinations, data flows reversing direction unexpectedly, and any direct internet egress from the historian host. A historian talking to the internet is an incident until proven otherwise.
6. **Hunt for living-off-the-land on the historian host.** Historians run on Windows or Linux — apply host monitoring: new services, scheduled tasks, unexpected processes, and credential-dumping indicators. Attackers love historians as beachheads because they're always on, rarely patched, and trusted by both IT and OT.
7. **Plan historian-specific incident response.** With operations, define: how to isolate the historian without losing process visibility (failover to redundant historian?), how to validate data integrity after an incident (which tags, what time range), and who authorizes historian restoration. Data integrity validation is the hard part — plan the queries in advance.

## Expected outputs

- A baselined historian interaction map with alerts on unauthorized access, bulk exports, and config changes.
- Data-integrity monitoring (no silent backfills or tag tampering) and boundary/replication alerting.
- A historian-specific IR plan with data-integrity validation procedures.

## Pitfalls

- Treating the historian as "just a database" — it's a high-value OT target with unique attack patterns.
- Monitoring without an operations partner — you'll misread maintenance as attacks and miss real manipulation.
- Allowing direct internet access "for vendor support" — the most common historian exposure.
- Patching without vendor/operations coordination — historian patches can break data collection.
- No data-integrity validation plan — after an incident, you can't prove the process data is trustworthy.

## References

- NIST SP 800-82 Rev. 3 (Guide to OT Security)
- MITRE ATT&CK for ICS — historian-related techniques (T0801, T0802, T0821)
- Historian vendor security guidance (AVEVA/OSIsoft PI security hardening)
- CISA ICS advisories for historian vulnerabilities
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
