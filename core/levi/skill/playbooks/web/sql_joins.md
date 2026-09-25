---
skill_id: web_sql_joins
name: SQL JOINs
description: Combine tables with INNER, LEFT, RIGHT, and FULL joins, and know which rows survive each one.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database]
version: 1.0.0
---
# SQL JOINs
## Purpose
Assemble related data across tables while keeping straight which rows appear and which vanish.
## Key ideas
- INNER JOIN keeps only rows with a match on both sides; it is the default mental model for related data.
- LEFT JOIN keeps every row from the left table, filling NULLs where the right side has no match.
- RIGHT JOIN mirrors LEFT; FULL OUTER JOIN keeps unmatched rows from both sides.
- Join on indexed foreign keys; joining on unindexed or mismatched-type columns is a performance trap.
- Duplicate join keys multiply rows (fan-out); aggregate before joining when the relationship is one-to-many.

## In practice
Choose the join by asking which side may be missing: orders with optional coupons is a LEFT JOIN from orders, because an order without a coupon must still appear. When counts look too high after a join, suspect fan-out from a one-to-many relationship and pre-aggregate the many side in a subquery first. Always qualify column names with table aliases in multi-table queries; id alone is ambiguous the moment two tables are involved. Test joins against data that includes the missing-match case, not just the happy path, because that is where INNER-vs-LEFT mistakes hide.

```sql
-- every order, with coupon code when one was used
SELECT o.id, o.total, c.code
FROM orders AS o
LEFT JOIN coupons AS c ON c.id = o.coupon_id
WHERE o.created_at >= '2026-01-01';

-- pre-aggregate the many side to avoid fan-out
SELECT u.id, u.name, s.order_count
FROM users AS u
LEFT JOIN (
  SELECT user_id, COUNT(*) AS order_count
  FROM orders GROUP BY user_id
) AS s ON s.user_id = u.id;
```

## Common mistakes
- Using INNER JOIN where unmatched rows must survive, silently dropping orders without coupons.
- Joining one-to-many without pre-aggregation and reporting inflated totals.
- Leaving columns unqualified so the query breaks the day a second id appears.

## Checklist
- Does the join type match which side may legitimately be missing?
- Is fan-out from one-to-many joins controlled with pre-aggregation?
- Are all columns qualified with table aliases?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
