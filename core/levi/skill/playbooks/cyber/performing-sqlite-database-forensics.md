---
skill_id: cyber_performing_sqlite_database_forensics
name: SQLite Database Forensics
description: Examine SQLite databases from applications and devices to recover records, deleted data, and timelines.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, sqlite, database]
version: 1.0.0
---

## Purpose
- Extract evidence from the SQLite databases that underpin mobile apps, browsers, and desktop applications.
- Recover deleted records and freelist pages that still hold evidentiary data.
- Build timelines from database timestamps correlated with file system and log evidence.

## When to use
- When application data on a device or disk image is relevant to an investigation.
- When browser history, chat messages, or location data must be recovered from app databases.
- When validating or challenging data exported by forensic tools.
- When deleted records may hold the key facts of a case.

## Prerequisites
- Forensic copies of the database files, including WAL and journal files, with hashes recorded.
- SQLite analysis tooling: DB Browser for SQLite, sqlite3 CLI, or forensic suites with SQLite parsing.
- Knowledge of the application's schema or the ability to reverse-engineer it.
- A working copy discipline: never analyze the original evidence file directly.

## Procedure
1. Verify hashes of the database, WAL, and journal files against acquisition records.
2. Work only on copies; checkpoint or merge WAL files on the copy so all committed data is visible.
3. Map the schema: tables, columns, indexes, and triggers relevant to the investigative questions.
4. Query the live tables for records in scope, documenting every query used.
5. Examine freelist pages and unallocated space for deleted records using forensic SQLite tools.
6. Parse WAL frames for recent transactions that may not yet be checkpointed.
7. Convert application-specific timestamps (epoch variants, Cocoa, WebKit) to a common timeline.
8. Correlate database events with file system timestamps, logs, and other evidence.
9. Validate tool output by spot-checking raw page content for critical findings.
10. Document findings with table names, record identifiers, queries used, and confidence levels.

## Expected outputs
- Recovered records including deleted data, with queries documented.
- A timeline of database events correlated with other evidence.
- Validation notes for tool-derived findings.
- A schema reference document for the application's database version analyzed.
- Tool validation notes comparing two independent parsers on key artifacts.

## Pitfalls
- Analyzing the database without its WAL file, which hides the most recent activity.
- Misconverting timestamps; SQLite databases use several epoch conventions and getting them wrong shifts timelines.
- Trusting forensic tool parsing without spot-checking raw data on critical findings.
- Forgetting timezone handling when the application stores local time.
- Overwriting the original database by opening it in a tool that checkpoints the WAL automatically.

## References
- SANS DFIR poster on SQLite forensics for quick reference
- SQLite official documentation on file format and WAL mode
- NIST SP 800-86 Guide to Integrating Forensic Techniques into Incident Response
- SANS FOR500 Windows forensic analysis materials on application artifacts
- Research literature on SQLite forensic recovery techniques
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
