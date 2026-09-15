---
skill_id: cyber_implementing_syslog_centralization_with_rsyslog
name: Implementing Syslog Centralization with rsyslog
description: Build a reliable, tamper-resistant centralized syslog pipeline using rsyslog.
risk: low
permissions: []
requires_confirmation: false
tags: [logging, syslog, rsyslog]
version: 1.0.0
---
## Purpose
This playbook walks through deploying rsyslog as the backbone of centralized log collection: encrypted transport, disk-assisted queues for reliability, structured parsing, and forwarding into long-term storage or a SIEM.

## When to use
- Logs live only on individual hosts and are lost when a system is wiped or compromised.
- Compliance requires centralized, time-synchronized, tamper-evident log retention.
- A SIEM needs a dependable ingestion tier that survives network or receiver outages.

## Prerequisites
- Time synchronization (NTP/Chrony) verified across all senders; log timestamps are useless without it.
- TLS certificates for the collector tier (internal CA or public).
- Capacity plan: estimated events per second, average message size, retention window.

## Procedure
1. **Design the topology.** Decide on direct-to-collector vs. relay tiers; use relays per datacenter or cloud region to reduce cross-WAN traffic and provide local buffering.
2. **Enable TLS transport.** Configure senders to use TLS (not plain TCP/UDP) with certificate validation; restrict the collector to accept only authenticated clients where feasible.
3. **Add disk-assisted queues.** Set up action queues with disk spooling on both senders and relays so bursts or collector outages do not lose messages.
4. **Normalize at ingest.** Parse with structured templates or mmjsonparse/mmnormalize so downstream systems receive consistent fields (hostname, app, severity, structured data).
5. **Filter noise early.** Drop or downsample known-noisy facility/priority combinations at the relay tier to protect SIEM license and storage.
6. **Protect log integrity.** Write a local tamper-evident copy (hash-chained or WORM storage) for high-value sources such as authentication and sudo logs.
7. **Monitor the pipeline.** Alert on queue depth growth, TLS handshake failures, EPS drops per source, and disk usage on spool directories — a silent logging outage is a detection outage.
8. **Test failover.** Simulate collector loss and network partitions; verify no messages are lost and ordering is preserved.

## Expected outputs
- Documented rsyslog topology with TLS and queue configuration under version control.
- Runbook for adding a new log source, including parsing rules and retention class.
- Monitoring dashboards and alerts for pipeline health.

## Pitfalls
- Plain UDP syslog across untrusted networks: trivially spoofable and lossy.
- Clock skew between senders making correlation impossible; fix NTP first.
- Unbounded queues filling disks; set queue size limits with documented overflow behavior.

## References
- rsyslog documentation (rsyslog.com/doc).
- NIST SP 800-92, Guide to Computer Security Log Management.
