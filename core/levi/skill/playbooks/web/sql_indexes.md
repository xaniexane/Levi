---
skill_id: web_sql_indexes
name: SQL Indexes
description: How indexes speed reads, cost writes, and which ones to create: B-tree basics, composite order, and covering.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database, performance]
version: 1.0.0
---
# SQL Indexes
## Purpose
Make common queries fast with indexes chosen from evidence, not superstition.
## Key ideas
- An index is a separate data structure the planner can use to find rows without scanning the table.
- B-tree indexes serve equality and range queries on the indexed columns' leading edge.
- Composite index column order matters: put the most selective, equality-filtered columns first.
- Indexes speed reads but cost on every write; each additional index taxes inserts and updates.
- Covering indexes include the selected columns so the query never touches the table at all.

## In practice
Create indexes from the slow-query log and EXPLAIN plans, not from guesses: find the query, confirm a sequential scan on a large table, then index the filtered and joined columns. Keep composite indexes ordered by how the queries actually filter (equality columns before range columns), and resist indexing every column; five targeted indexes beat twenty hopeful ones. Revisit periodically: unused indexes are pure write overhead, and changing query patterns orphan old ones. For write-heavy tables, measure insert throughput before and after adding an index so the trade is explicit.

```sql
-- equality on status, range on created_at: equality column first
CREATE INDEX idx_orders_status_created
  ON orders (status, created_at);

-- covering index: the query's columns all come from the index
CREATE INDEX idx_orders_user_cover
  ON orders (user_id) INCLUDE (status, total);

-- check what the planner will actually do
EXPLAIN SELECT id FROM orders
WHERE status = 'shipped' AND created_at >= '2026-01-01';
```

## Common mistakes
- Indexing every column individually instead of designing composite indexes for real queries.
- Putting range-filtered columns first in composite indexes, stranding the later columns.
- Never dropping unused indexes, paying write overhead for reads that never come.

## Checklist
- Is each index justified by a measured slow query or EXPLAIN plan?
- Are composite indexes ordered equality-first, matching actual filters?
- Are unused indexes identified and removed on a schedule?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
