---
skill_id: red_database_collection_test
name: Database Collection Test
description: Test database dumping and query patterns to validate database-activity monitoring.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, database, monitoring]
version: 1.0.0
team: red
tests_blue: cyber_performing_sqlite_database_forensics
---
# Database Collection Test

## Purpose

Databases hold the crown jewels in queryable form. This test performs canary database
dumps and anomalous query patterns against test databases, validating database-activity
monitoring and access controls.

## When to use

- During collection phases where databases are in scope.
- To validate DAM tooling and query-anomaly alerting.
- To test backup-file security as the alternate collection path.

## Prerequisites

- Authorization for the test databases; canary data.
- DBA coordination for monitoring verification.

## Procedure

1. Perform canary dumps (full and selective) via standard tooling; record telemetry.
2. Run anomalous query patterns: full-table scans, off-hours bulk selects, new-client
   connections.
3. Test backup-file access: are backup files readable by the test context?
4. Record which activities the DAM/monitoring flagged and which were silent.
5. Verify no canary data left the test database scope.
6. Deliver the database-monitoring assessment.

## Expected outputs

- Dump and query-pattern detection results.
- Backup-file access findings.
- DAM coverage assessment.

## Pitfalls

- Dumping production databases — test databases with canary data only.
- Bulk queries that load production-adjacent systems — coordinate timing.

## References

- MITRE ATT&CK: Automated Collection; database-security literature.

## Blue-team control under test

This playbook validates their database-activity monitoring is under test — silent bulk
extraction is the DAM gap. Paired blue-team counterpart:
`cyber_performing_sqlite_database_forensics`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
