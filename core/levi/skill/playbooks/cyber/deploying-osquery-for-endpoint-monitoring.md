---
skill_id: cyber_deploying_osquery_for_endpoint_monitoring
name: Deploying osquery for Endpoint Monitoring
description: Deploy osquery fleet-wide with scheduled queries and packs that turn endpoints into queryable detection sensors.
risk: low
permissions: []
requires_confirmation: false
tags: [endpoint, monitoring, detection]
version: 1.0.0
---
## Purpose

Turn every endpoint into a SQL-queryable sensor with osquery: scheduled queries for persistence, process, network, and configuration telemetry, shipped to your pipeline for detection and hunting. osquery is the free, cross-platform way to answer "what's true on this host right now" at scale.

## When to use

- Building endpoint visibility without (or alongside) a commercial EDR.
- Fleet-wide hunting and compliance checks ("which hosts have this vulnerable software?").
- Incident response triage across many hosts with a single query.
- Validating configuration baselines continuously rather than at audit time.

## Prerequisites

- A deployment mechanism (SCCM/Intune/MDM, Ansible/Puppet/Chef, or gold images) and a log pipeline (TLS endpoint, Kafka, or SIEM ingestion).
- Fleet manager decision: osquery with TLS enrollment (FleetDM, Kolide) versus standalone scheduled queries — pick one and standardize.
- Baseline knowledge of normal fleet state (standard software, expected services) for writing meaningful queries.
- Performance budget: osquery is light, but badly written queries (full filesystem scans every minute) are not.

## Procedure

1. **Deploy with a minimal, safe flag set.** Install osquery with TLS enrollment to your fleet manager, a sensible config interval (60s), and logger TLS. Verify enrollment and check-in from a pilot group before fleet rollout. Pin the osquery version and test upgrades in the pilot ring first.
2. **Start with the high-value query packs.** Enable curated packs covering: startup items and persistence (`startup_items`, `launchd`, scheduled tasks, services), listening processes and established connections, logged-in users, browser extensions, and installed software inventory. These answer the questions IR asks first.
3. **Write custom queries for your environment.** Add queries for org-specific risks: unauthorized remote-access tools (TeamViewer, AnyDesk processes), USB device history, firewall status, disk encryption state, and EDR sensor health (is the commercial agent running?). Each query gets a documented purpose and an expected-result baseline.
4. **Schedule by cost and value.** High-value, cheap queries (processes, listening ports) run every 60–300 seconds; expensive ones (file inventory, full software lists) run hourly or on-demand via distributed queries. Measure per-query execution time in the pilot and kill anything that spikes CPU.
5. **Ship results to detection, not just storage.** Forward osquery result logs to the SIEM and build alerts on deltas: new persistence entries, new listening processes, new users, EDR agent stopped. osquery's differential queries are purpose-built for "what changed" detection — use them.
6. **Use distributed queries for incident response.** When an incident hits, push one-off queries fleet-wide: hunt for the malicious hash, the rogue scheduled task, the suspicious listening port. This is osquery's superpower — fleet-wide answers in minutes without touching each host.
7. **Maintain query hygiene.** Quarterly: review query performance, retire queries with no detection value, update packs for new OS versions, and verify the TLS enrollment and log pipeline health. Track fleet coverage (enrolled and reporting) as a metric — unenrolled hosts are blind spots.

## Expected outputs

- Fleet-wide osquery enrollment with curated packs and org-specific custom queries.
- SIEM alerts on persistence, network, and configuration deltas via differential queries.
- Distributed-query IR capability and quarterly query-hygiene reviews with coverage metrics.

## Pitfalls

- Filesystem-scan queries on tight schedules — CPU spikes and user complaints, then the agent gets uninstalled.
- Collecting without alerting — terabytes of osquery logs nobody queries is expensive noise.
- No enrollment monitoring — hosts silently drop off and you discover the gap during an incident.
- Custom queries written against one OS version that break silently on the next.
- Treating osquery as a replacement for behavioral EDR — it's a visibility layer; pair it with prevention.

## References

- osquery documentation (osquery.io) — schema, configuration, deployment
- FleetDM / Kolide Fleet documentation for fleet management
- Palantir / Trail of Bits osquery deployment guidance and query packs
- MITRE ATT&CK — map queries to techniques for coverage tracking
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
