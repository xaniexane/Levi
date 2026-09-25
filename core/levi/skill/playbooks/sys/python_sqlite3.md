---
skill_id: sys_python_sqlite3
name: Python sqlite3
description: Embedded SQL with the stdlib: connections, parameters, and transactions.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python sqlite3

## Purpose

Embedded SQL with the stdlib: connections, parameters, and transactions.

## Overview

sqlite3 gives you a full SQL database in a single file with zero setup - ideal for local tools, caches, and prototypes. Connect with sqlite3.connect(path); use the connection as a context manager to commit or roll back transactions automatically. Always use parameterized queries (cursor.execute('... WHERE id = ?', (user_id,))) - never interpolate values into SQL strings, which is textbook injection. executemany batch-inserts efficiently. Row factories (conn.row_factory = sqlite3.Row) give dict-like column access instead of bare tuples. Transactions: the with conn block commits on clean exit and rolls back on exception - batch related writes together for both speed and atomicity. Pragmas tune behavior: journal_mode=WAL for concurrent readers, foreign_keys=ON to actually enforce foreign keys (off by default). Type notes: SQLite is dynamically typed; Python types map to storage classes, and datetime needs adapters or ISO strings. Concurrency: one writer at a time; keep transactions short, and for heavy multi-process write loads consider a client-server database instead. Back up with the backup API or plain file copy when no transaction is active.

## Quick reference

- sqlite3.connect(path): zero-setup embedded database.

- Parameterized queries (?, ...) always - never interpolate values into SQL.

- with conn: commits on success, rolls back on exception.

- row_factory = sqlite3.Row: dict-like rows.

- PRAGMA journal_mode=WAL for readers; PRAGMA foreign_keys=ON to enforce.

- One writer at a time; keep transactions short.


## Worked example

Safe inserts and transactional batch writes:

```
import sqlite3

conn = sqlite3.connect('app.db')
conn.execute('PRAGMA foreign_keys = ON')
conn.row_factory = sqlite3.Row

with conn:
    conn.execute('CREATE TABLE IF NOT EXISTS users'
                 '(id INTEGER PRIMARY KEY, name TEXT)')
    conn.executemany('INSERT INTO users(name) VALUES (?)',
                   [('ada',), ('bo',)])

row = conn.execute('SELECT * FROM users WHERE name = ?',
                 ('ada',)).fetchone()
print(row['id'], row['name'])
conn.close()
```

- ? placeholders keep user data out of the SQL text: no injection.

- The with conn block commits both statements atomically.

- Row factory lets us use row['name'] instead of row[1].


## Common mistakes

- f-string SQL with user data: injection vulnerability.
  Fix: Always use ? placeholders with parameter tuples.

- Forgetting to commit: changes silently lost on close.
  Fix: Use the with conn: block so commit/rollback is automatic.


## Quick checks

Q: When does sqlite stop being enough?
A: Multiple concurrent writers, high write throughput, or data bigger than comfortable single-file size. For one app, one writer, local data - it is plenty, and it runs everywhere.


Q: Why are my foreign keys not enforced?
A: SQLite parses but ignores foreign key constraints unless PRAGMA foreign_keys = ON is set per connection. Set it right after connect.


## Mental model

sqlite3 is a filing cabinet in your office: no server room, no DBA, just open a drawer (connect) and file things. Parameterized queries are the labeled folders - you never scribble a visitor's name directly onto the cabinet's lock mechanism.
