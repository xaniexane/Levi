---
skill_id: web_http_methods
name: HTTP Methods
description: Learn what GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS each promise about safety and idempotency.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Methods
## Purpose
Choose the right method for each operation so that caches, retries, proxies, and other developers can reason about your API without reading its source code.
## Key ideas
- GET retrieves a representation and must not change server state; it is both safe and idempotent.
- POST submits data for processing; it is neither safe nor idempotent, so clients should not blindly retry it.
- PUT replaces a resource wholesale and DELETE removes one; both are idempotent, so retrying them is harmless.
- PATCH applies a partial change; whether it is idempotent depends on the patch format, so document it.
- HEAD behaves like GET but returns headers only, useful for checking existence or size; OPTIONS describes what methods a resource supports.

## In practice
Map your operations to methods by asking two questions: does it change anything, and does repeating it cause harm. Reads and searches are GET. Creating something new where the server assigns the identity is POST. Replacing a known resource at a known URL is PUT. Tweaking a few fields is PATCH. Removing is DELETE. This is not decoration: a crawler or prefetch may fire GETs speculatively, a proxy may cache them, and a client may retry a failed PUT, all assuming the method contract holds. Break the contract and you get duplicated charges, lost updates, or cached writes.

```http
# Safe to retry: same result no matter how many times it runs
PUT /api/users/42 HTTP/1.1
Content-Type: application/json

{"name": "Mara", "role": "editor"}

# Not safe to retry blindly: could create a duplicate
POST /api/orders HTTP/1.1
Content-Type: application/json

{"item": "notebook", "qty": 1}
```

## Common mistakes
- Using GET for actions that change state, such as /delete?id=5, which crawlers, prefetchers, and caches may trigger.
- Using POST for everything out of habit, throwing away the caching and retry semantics the other methods provide.
- Making DELETE non-idempotent by returning an error when the resource is already gone instead of succeeding quietly.

## Checklist
- Is every read-only operation a GET with no side effects?
- Are destructive or duplicating operations on POST with retry protection?
- Do your PUT and DELETE handlers behave the same when repeated?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
