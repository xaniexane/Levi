---
skill_id: web_js_promises_async
name: JavaScript Promises and Async
description: The async model: promises, async/await, error propagation, and running operations in parallel.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend]
version: 1.0.0
---
# JavaScript Promises and Async
## Purpose
Write asynchronous code that reads top-to-bottom and fails loudly instead of silently.
## Key ideas
- A promise represents a future value with three states: pending, fulfilled, rejected.
- async/await lets you write async logic in straight-line style; await pauses only that function.
- Errors in awaited promises propagate like thrown exceptions; catch them with try/catch.
- Promise.all runs independent operations concurrently and fails fast on the first rejection.
- An unhandled rejection is a bug that reports itself late; always attach error handling.

## In practice
Mark functions async when they await, and await every promise you create or return it to the caller; a floating promise is a silent failure waiting to happen. Use try/catch around awaits the way you would around any fallible operation, and keep the catch close to the operation so error context is fresh. Reach for Promise.all when operations are independent (fetching three resources), but stay sequential when order or shared state matters. Never mix raw .then chains with await in the same function without reason; pick one style per function and the error paths stay readable.

```javascript
async function loadDashboard(userId) {
  try {
    const [user, orders] = await Promise.all([
      fetch(`/api/users/${userId}`).then(r => r.json()),
      fetch(`/api/users/${userId}/orders`).then(r => r.json()),
    ]);
    return { user, orders };
  } catch (err) {
    console.error("dashboard load failed", err);
    throw err; // let the caller decide: retry, toast, or redirect
  }
}
```

## Common mistakes
- Forgetting await and operating on a promise object instead of its value.
- Leaving promise rejections unhandled, producing silent failures and console noise.
- Awaiting independent operations one by one, turning parallel work into a slow queue.

## Checklist
- Is every created promise awaited, returned, or explicitly handled?
- Are independent awaits grouped with Promise.all?
- Do async functions surface errors to callers instead of swallowing them?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
