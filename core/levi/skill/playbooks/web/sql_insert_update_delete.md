---
skill_id: web_sql_insert_update_delete
name: SQL INSERT, UPDATE, DELETE
description: Write data safely: targeted writes, the WHERE clause that must never be missing, and returning clauses.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database]
version: 1.0.0
---
# SQL INSERT, UPDATE, DELETE
## Purpose
Change data deliberately, with guardrails against the one missing WHERE that ruins a table.
## Key ideas
- INSERT names its columns explicitly so schema changes do not silently shift values into wrong columns.
- UPDATE and DELETE without WHERE affect every row; always write WHERE first, then the rest of the statement.
- RETURNING gives back the changed rows (ids, timestamps) without a second query.
- Prefer soft deletes (a deleted_at flag) when history matters; hard deletes are forever.
- Wrap multi-statement changes in a transaction so partial writes cannot persist.

## In practice
Make the dangerous statements boring: write the WHERE clause before anything else, then run the same WHERE as a SELECT to preview the affected rows, and only then execute the write. Use RETURNING to capture generated ids and timestamps in the same round trip. For bulk updates, batch in manageable chunks with pauses rather than one giant statement that locks the table and bloats the transaction log. Keep an audit trail for sensitive writes (who, when, old value, new value); the day someone asks what happened to the data, the log is the only witness.

```sql
-- write WHERE first, preview as SELECT, then execute
SELECT id FROM orders WHERE status = 'draft' AND created_at < '2026-01-01';

UPDATE orders
SET status = 'expired'
WHERE status = 'draft' AND created_at < '2026-01-01'
RETURNING id, status;

INSERT INTO users (email, name) VALUES ('mara@example.com', 'Mara')
RETURNING id, created_at;
```

## Common mistakes
- Running UPDATE or DELETE without WHERE and modifying the entire table.
- Using positional INSERT without column names, so new columns corrupt the mapping.
- Hard-deleting rows that regulations or debugging later require you to produce.

## Checklist
- Is the WHERE clause written and previewed before every bulk write?
- Do INSERTs name columns explicitly and use RETURNING for generated values?
- Are destructive writes audited or soft-deleted where history matters?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
