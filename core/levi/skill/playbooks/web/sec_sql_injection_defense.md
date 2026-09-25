---
skill_id: web_sec_sql_injection_defense
name: SQL Injection Defense
description: Keep SQL injection structurally impossible: parameterized queries, least privilege, and ORM hygiene.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web, sql]
version: 1.0.0
---
# SQL Injection Defense
## Purpose
Eliminate the most classic web vulnerability class through construction, not vigilance.
## Key ideas
- Parameterized queries separate code from data at the protocol level; injection becomes impossible by construction.
- The vulnerability is string concatenation of input into SQL; the fix is never concatenating input into SQL.
- Dynamic identifiers (table/column names) cannot be parameterized; map them through a strict whitelist.
- Database accounts for the app should have least privilege: no DROP, no admin, ideally no direct table writes beyond need.
- ORM raw-query escapes need the same review as hand-written SQL; the ORM only protects the paths you let it.

## In practice
Ban string-built SQL in code review; make the linter or reviewer ask 'where do the values come from' for every query. Run the application database user with minimal grants so even a successful injection finds little to exploit: read and write on its tables, nothing administrative. Turn on query logging in staging and review for interpolated values; parameterized queries show placeholders, concatenated ones show data baked into the text. Include injection payloads in your automated test suite as regression tests for the parameterization discipline, not as proof any single query is safe.

```python
import sqlite3
db = sqlite3.connect("app.db")

# SAFE: value bound as a parameter, never parsed as SQL
user = db.execute(
    "SELECT id, name FROM users WHERE email = ?",
    (email_from_request,),
).fetchone()

# For dynamic sort columns: whitelist, never interpolate
ALLOWED_SORT = {"name": "name", "created": "created_at"}
sort_col = ALLOWED_SORT.get(requested_sort, "created_at")
rows = db.execute(f"SELECT id, name FROM users ORDER BY {sort_col}").fetchall()
```

## Common mistakes
- Building queries with f-strings or concatenation anywhere user input flows.
- Interpolating sort columns or table names without a whitelist.
- Running the app as a database superuser, maximizing blast radius.

## Checklist
- Is every value passed as a bound parameter with zero string-built SQL?
- Are dynamic identifiers restricted to a whitelist?
- Does the app database user hold least privilege?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
