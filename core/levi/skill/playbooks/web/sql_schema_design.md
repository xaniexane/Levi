---
skill_id: web_sql_schema_design
name: SQL Schema Design
description: Design tables that stay correct: primary keys, foreign keys, types, constraints, and defaults.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database, design]
version: 1.0.0
---
# SQL Schema Design
## Purpose
Create schemas where invalid data is rejected by the database, not discovered by users.
## Key ideas
- Every table gets a primary key; surrogate integer or UUID keys keep identity stable when business keys change.
- Foreign keys declare relationships and, with the right actions, prevent or cascade orphaned rows.
- Choose the narrowest correct type: integers for counts, numeric for money, timestamptz for instants.
- NOT NULL, UNIQUE, and CHECK constraints encode the rules so bad data cannot be inserted at all.
- Sensible defaults (created_at now(), status 'draft') remove whole categories of missing-value bugs.

## In practice
Design from the invariants, not the forms: what must always be true (an order has a user, totals are non-negative, emails are unique) becomes constraints, and the application never has to enforce what the database guarantees. Prefer timestamptz over naive timestamps so every instant is unambiguous across time zones. Add foreign keys even when the ORM manages relations; the database is the last line of defense when a script bypasses the app. Review every nullable column and ask whether NULL is meaningful or just unconsidered; unconsidered NULLs become the three-valued-logic bugs of next quarter.

```sql
CREATE TABLE orders (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  status     TEXT NOT NULL DEFAULT 'draft'
             CHECK (status IN ('draft','paid','shipped','cancelled')),
  total      NUMERIC(12,2) NOT NULL CHECK (total >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, created_at)
);
```

## Common mistakes
- Storing money as floating point and accumulating rounding errors in financial totals.
- Using naive timestamps and discovering daylight-saving ambiguity in the audit trail.
- Skipping foreign keys and constraints, letting orphans and invalid states accumulate.

## Checklist
- Does every table have a primary key and declared foreign keys?
- Are money, time, and identity using the correct narrow types?
- Do constraints encode the invariants so bad data is rejected at insert?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
