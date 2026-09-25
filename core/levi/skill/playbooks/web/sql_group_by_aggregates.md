---
skill_id: web_sql_group_by_aggregates
name: SQL GROUP BY and Aggregates
description: Summarize data with COUNT, SUM, AVG, MIN, MAX, group it with GROUP BY, and filter groups with HAVING.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database]
version: 1.0.0
---
# SQL GROUP BY and Aggregates
## Purpose
Turn raw rows into answers: totals, averages, and per-group breakdowns computed where the data lives.
## Key ideas
- Aggregates collapse rows: COUNT counts, SUM/AVG total and average numerics, MIN/MAX find extremes.
- GROUP BY partitions rows first, then aggregates each group separately.
- HAVING filters groups after aggregation; WHERE filters rows before it.
- COUNT(*) counts rows, COUNT(column) skips NULLs in that column: know which you mean.
- Every non-aggregated column in the SELECT must appear in the GROUP BY (or be functionally dependent).

## In practice
Think in two passes: WHERE trims the raw rows, GROUP BY plus aggregates summarize what remains, HAVING trims the groups. When an average looks wrong, check whether NULLs or zero-rows are skewing it, and whether you needed a weighted average instead. Put the grouping key and the aggregates in the SELECT together so the result is self-describing: month, order_count, revenue. For dashboards, prefer computing these summaries in SQL over fetching raw rows; the database is built for this and the network is not built for a million rows of raw material.

```sql
SELECT
  date_trunc('month', created_at) AS month,
  COUNT(*)        AS orders,
  SUM(total)      AS revenue,
  AVG(total)      AS avg_order
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY 1
HAVING COUNT(*) > 10
ORDER BY 1;
```

## Common mistakes
- Using WHERE on an aggregate (WHERE COUNT(*) > 10) instead of HAVING.
- Mixing COUNT(*) and COUNT(column) without noticing NULLs change the answer.
- Selecting non-grouped, non-aggregated columns and getting arbitrary values per group.

## Checklist
- Is row filtering in WHERE and group filtering in HAVING?
- Do the COUNT/SUM semantics match the question being asked?
- Are summaries computed in SQL rather than shipped as raw rows?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
