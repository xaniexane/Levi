---
skill_id: web_sql_transactions
name: SQL Transactions
description: ACID transactions: BEGIN/COMMIT/ROLLBACK, isolation levels, and keeping transactions short.
risk: info
permissions: []
requires_confirmation: false
tags: [sql, database]
version: 1.0.0
---
# SQL Transactions
## Purpose
Keep multi-statement changes atomic and consistent even when errors or concurrency strike.
## Key ideas
- A transaction groups statements into one atomic unit: all commit together or all roll back.
- ACID promises atomicity, consistency, isolation, and durability for committed work.
- Isolation levels trade correctness against concurrency; read committed is the common default.
- Long transactions hold locks and bloat; do the work, commit promptly, never wait on users mid-transaction.
- Deadlocks happen when transactions lock in different orders; consistent lock ordering prevents most.

## In practice
Wrap every multi-statement business operation (create order plus decrement stock plus record payment) in a single transaction, and keep it short: gather inputs first, then open, write, commit. Never hold a transaction across user input, network calls, or sleep; that is how lock queues form and pages fire. On error, roll back and let the caller decide whether retrying is safe; half-applied business operations are worse than failed ones. When deadlocks appear, look for inconsistent lock ordering across code paths and make every path touch tables in the same sequence.

```sql
BEGIN;
  UPDATE inventory SET qty = qty - 1
   WHERE sku = 'NB-001' AND qty >= 1;
  INSERT INTO orders (user_id, total) VALUES (42, 29.99)
  RETURNING id;
COMMIT;
-- on any error: ROLLBACK; and the inventory update vanishes too
```

## Common mistakes
- Leaving related writes outside a transaction, so failures leave half-applied business operations.
- Holding transactions open across network calls or user waits, causing lock pileups.
- Catching errors and committing anyway, persisting the partial work the rollback would have undone.

## Checklist
- Is every multi-statement business operation in one transaction?
- Do transactions avoid network calls, sleeps, and user waits?
- Are errors rolled back with an explicit retry policy?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
