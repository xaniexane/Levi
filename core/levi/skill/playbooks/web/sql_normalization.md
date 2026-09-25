---
skill_id: web_sql_normalization
name: SQL Normalization
description: First through third normal form: eliminating redundancy so each fact lives in exactly one place.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database, design]
version: 1.0.0
---
# SQL Normalization
## Purpose
Design tables where updates change one row, not a scattered set of copies that drift apart.
## Key ideas
- First normal form: atomic values, one value per cell, no repeating groups.
- Second normal form: every non-key column depends on the whole key, not part of a composite key.
- Third normal form: non-key columns depend only on the key, not on other non-key columns.
- Normalization kills update anomalies: change a customer's address once, not in every order row.
- Denormalize deliberately for read performance, with a plan for keeping copies in sync.

## In practice
Normalize first, then denormalize with a written reason: the report that needs one fast query, the read model refreshed nightly. Each denormalized copy needs an owner and a sync mechanism (trigger, job, or event), or it will drift and the two sources will disagree in front of a customer. Watch for the classic smell of repeated groups (phone1, phone2, phone3 columns) and transitive dependencies (storing city when zip determines it); both are future anomalies. Document which tables are intentionally denormalized so the next developer does not 'fix' them back into slowness or, worse, trust the stale copy.

```sql
-- 3NF: customer facts live once in customers, not in every order
CREATE TABLE customers (
  id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email   TEXT NOT NULL UNIQUE,
  address TEXT NOT NULL
);
CREATE TABLE orders (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  total       NUMERIC(12,2) NOT NULL
);
-- changing an address updates one row, and history stays consistent
```

## Common mistakes
- Storing the same fact in many rows and watching copies diverge after partial updates.
- Repeating groups as numbered columns (phone1, phone2) instead of a child table.
- Denormalizing for speed with no sync plan, then serving stale data as truth.

## Checklist
- Does each fact live in exactly one place unless deliberately denormalized?
- Are repeating groups modeled as child tables?
- Does every denormalized copy have an owner and a sync mechanism?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
