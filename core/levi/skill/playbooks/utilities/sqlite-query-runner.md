---
skill_id: utility.sqlite_query_runner
name: SQLite Query Runner
description: Run read-only SELECT queries against a SQLite database and display the rows.
risk: low
permissions: []
requires_confirmation: false
tags: [sqlite, database, query]
version: 1.0.0
---

# SQLite Query Runner

SQLite Query Runner opens a database in read-only mode, runs your SELECT query, and displays the rows as a table. Anything that is not a SELECT is refused outright.

## When to use

- Inspecting rows in a local app database.
- Answering a quick question from stored data.
- Verifying a migration's results without touching the data.

## Steps

1. Open the database read-only via the sqlite3 URI mode=ro flag - the file cannot be modified even by accident.
2. Accept only statements beginning with SELECT or WITH; refuse INSERT, UPDATE, DELETE, DROP, and friends with a clear message.
3. Run the query with a row limit (default 100) and display results as an aligned table.
4. Report the row count; close the connection.

## Honest limits

- Standard library only (sqlite3).
- SELECT-only by design: this skill cannot write, and that is a feature.
- Read-only mode also blocks locking surprises on databases another process has open.

Original work authored for LEVI - utilities pack.
