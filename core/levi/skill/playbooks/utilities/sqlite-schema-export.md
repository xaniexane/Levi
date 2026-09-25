---
skill_id: utility.sqlite_schema_export
name: SQLite Schema Export
description: Export a SQLite database's schema (CREATE statements) to a .sql file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [sqlite, database, schema, export]
version: 1.0.0
---

# SQLite Schema Export

SQLite Schema Export reads sqlite_master and writes every table, index, view, and trigger definition to a .sql file - the database's blueprint, without its data.

## When to use

- Documenting a database's structure.
- Diffing schemas between two database versions.
- Bootstrapping an empty database with the same shape.

## Steps

1. Open the database read-only.
2. Query sqlite_master for all CREATE statements in dependency-safe order (tables, then indexes, views, triggers).
3. Write the statements to a .sql file with a header noting source and date.
4. Verify the file parses by loading it into an empty in-memory database.

## Honest limits

- Standard library only (sqlite3).
- Schema only - no data rows are exported; say so plainly so nobody mistakes it for a backup.
- For a full backup including data, use the .dump route instead.

Original work authored for LEVI - utilities pack.
