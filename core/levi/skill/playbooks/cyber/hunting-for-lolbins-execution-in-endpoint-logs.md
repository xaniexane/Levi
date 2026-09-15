---
skill_id: cyber_hunting_for_lolbins_execution_in_endpoint_logs
name: Hunting for LOLBins Execution in Endpoint Logs
description: Operational guide to querying EDR/Sysmon logs for LOLBin execution anomalies: argument analytics, rarity scoring, and triage workflow.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, lolbins, edr]
version: 1.0.0
---
## Purpose

A companion to the LOLBin concept playbook, this is the operational
query guide: how to actually hunt LOLBin executions in EDR and Sysmon
logs at scale — query patterns, rarity scoring, argument analytics, and
a triage workflow that keeps analysts efficient without missing real
abuse.

## When to use

- Running the day-to-day LOLBin hunt from your SIEM or EDR console.
- Building scheduled LOLBin analytics with managed alert volume.
- Training analysts on LOLBin triage.
- Measuring LOLBin visibility coverage across the fleet.

## Prerequisites

- Centralized process-creation logs with command lines from the fleet
  (Sysmon/EDR), queryable in your SIEM.
- The per-binary suspicious-argument library from the LOLBin hunting
  playbook and the LOLBAS reference.
- A triage queue and disposition taxonomy (benign / suspicious /
  malicious / needs-more-data).
- Query-performance awareness: LOLBin hunts over long windows are
  expensive — design queries to be selective.

## Procedure

1. **Build the target binary list.** Start with the highest-risk
   LOLBins for your environment (downloaders, script hosts, installer
   abusers). Keep the list versioned — it grows as hunts reveal new
   abuse.
2. **Write argument-aware queries.** For each binary, query on
   (process name + suspicious argument patterns), not the name alone.
   Use case-insensitive matching and cover common obfuscations
   (caret-escaping in cmd, case variation, short-flag forms).
3. **Add rarity scoring.** Rank results by rarity: how often does this
   (binary, argument-pattern, parent) combination occur fleet-wide?
   Rare combinations from unusual parents go to the top of the triage
   queue; common deployment-tooling patterns sink.
4. **Enrich automatically.** For each hit, pull the parent chain,
   grandparent, user, host role, file hash, signer status, and any
   network connections within the following minutes. Triage with
   context, not isolated events.
5. **Triage in batches by pattern.** Group identical (binary, args,
   parent) patterns and disposition the pattern once — most LOLBin
   volume collapses into a handful of legitimate patterns. Document
   each pattern's justification.
6. **Escalate the unexplained.** Patterns that cannot be tied to
   legitimate tooling, especially with network activity or
   persistence-adjacent follow-on, go to incident response with the
   full enrichment package.
7. **Schedule and tune.** Convert the hunt into scheduled analytics
   with alert thresholds based on measured precision. Review and tune
   monthly — software changes shift the legitimate patterns.
8. **Measure coverage.** Track what percentage of the fleet contributes
   command-line telemetry; hunts are only as complete as the logging.
   Report coverage gaps as a security metric.

## Expected outputs

- Versioned LOLBin query pack with argument patterns per binary.
- Triage dispositions by pattern with justifications.
- Escalations with enrichment packages.
- Scheduled analytics with precision/recall tracking.
- Fleet command-line-logging coverage metrics.

## Pitfalls

- Querying raw process names without arguments floods the queue —
   argument-awareness is what makes this operational.
- Case-sensitivity and obfuscation variants (e.g. `c^e^r^t^u^t^i^l`)
   evade naive string matches — normalize before matching.
- Triage fatigue from re-reviewing the same legitimate patterns —
   pattern-level dispositioning with documentation prevents this.
- EDR query limits truncate long-window hunts — chunk by time or host
   group for completeness.
- Stale binary lists miss new abuse — review and extend the list from
   hunt findings and LOLBAS updates.

## References

- LOLBAS project (binary and argument-abuse reference)
- MITRE ATT&CK: T1218 (System Binary Proxy Execution)
- SIEM/EDR vendor documentation for process-telemetry query syntax
- The companion playbook: Hunting for Living-off-the-Land Binaries
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
