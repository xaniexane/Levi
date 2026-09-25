---
skill_id: web_sql_parameterized_queries
name: SQL Parameterized Queries
description: Separate code from data with bound parameters: the primary defense against SQL injection.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database, security]
version: 1.0.0
---
# SQL Parameterized Queries
## Purpose
Make SQL injection structurally impossible by never building queries from string concatenation.
## Key ideas
- Parameters ($1, ?, :name) send values separately from the SQL text; the database never parses values as code.
- String concatenation of user input into SQL is the vulnerability; parameterization is the fix.
- Parameters handle quoting and escaping for every type, including the edge cases hand-rolled escaping misses.
- Table and column names cannot be parameterized; validate identifiers against a whitelist instead.
- ORMs parameterize automatically until you use raw fragments; audit every raw() and literal for injection.

## In practice
Treat any query built with string interpolation as a defect until proven otherwise; grep for it in reviews. Use the driver's parameter style consistently and pass values as an array or object, never by formatting them into the SQL string. When identifiers must be dynamic (sort columns, table names), map user input through a whitelist dictionary to known-safe names. Log queries with placeholders intact rather than interpolated values; interpolated logs teach developers that concatenation is normal and occasionally leak data.

```javascript
// VULNERABLE: input becomes part of the SQL text
const bad = `SELECT * FROM users WHERE email = '${email}'`;

// SAFE: value travels separately, never parsed as SQL
const good = {
  text: "SELECT id, name FROM users WHERE email = $1 AND active = $2",
  values: [email, true],
};
const { rows } = await db.query(good.text, good.values);
```

## Common mistakes
- Concatenating user input into SQL strings, the textbook injection vulnerability.
- Parameterizing values but interpolating column names, leaving identifier injection open.
- Assuming the ORM makes raw fragments safe; raw SQL in ORMs is still raw SQL.

## Checklist
- Is every query's user input passed as bound parameters?
- Are dynamic identifiers validated against a whitelist?
- Do code reviews grep for string-built SQL?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
