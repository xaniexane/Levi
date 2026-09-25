---
skill_id: web_sql_select_where
name: SQL SELECT and WHERE
description: Read data precisely: column lists, filtering with WHERE, and the operators that express conditions.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database]
version: 1.0.0
---
# SQL SELECT and WHERE
## Purpose
Query tables with surgical precision instead of pulling everything and filtering in application code.
## Key ideas
- Name the columns you need; SELECT * is fine for exploration but wasteful and brittle in applications.
- WHERE filters rows before any grouping or ordering; put the most selective conditions where indexes can use them.
- NULL needs IS NULL / IS NOT NULL; equality against NULL is never true.
- IN, BETWEEN, and LIKE express set membership, ranges, and patterns; leading wildcards defeat indexes.
- ORDER BY plus LIMIT gives you top-N queries; without ORDER BY, row order is undefined.

## In practice
Write queries that ask the database for exactly what the feature needs: the right columns, the right rows, in the right order, paged with LIMIT. When a query is slow, read its EXPLAIN plan before guessing; most slow queries are missing an index or filtering on a transformed column the index cannot serve. Treat NULL deliberately in every condition, because a single unexpected NULL can silently drop rows from results. Keep exploratory SELECT * in the console and explicit column lists in shipped code, so a schema change adds a column without changing your application's shape.

```sql
SELECT id, name, total, created_at
FROM orders
WHERE status = 'shipped'
  AND created_at >= '2026-01-01'
  AND total IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;

-- pattern match; note the leading % cannot use a plain index
SELECT id, email FROM users WHERE email LIKE '%@example.com';
```

## Common mistakes
- Shipping SELECT * in application code, coupling every feature to every schema change.
- Comparing with = NULL and silently getting zero rows instead of using IS NULL.
- Filtering in application code what WHERE could have filtered in the database.

## Checklist
- Do shipped queries list explicit columns instead of SELECT *?
- Is NULL handled deliberately in every condition?
- Is row order deterministic wherever the feature depends on it?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
