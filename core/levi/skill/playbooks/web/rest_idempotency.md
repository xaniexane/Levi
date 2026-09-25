---
skill_id: web_rest_idempotency
name: REST Idempotency
description: Make retries safe with idempotent methods and idempotency keys on the operations that are not.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Idempotency
## Purpose
Let clients retry failed requests without fear of double charges, duplicate orders, or partial writes.
## Key ideas
- GET, PUT, DELETE, HEAD, and OPTIONS are idempotent by contract; repeating them must not change the outcome.
- POST is not idempotent, which is exactly why payment and order endpoints need idempotency keys.
- An idempotency key is a client-generated token sent per operation; the server stores the first result and replays it for repeats.
- Keys must expire (24 to 72 hours is typical) so storage stays bounded and old operations cannot be replayed forever.
- The response to a replayed key should be identical to the original, including the status code.

## In practice
Accept an Idempotency-Key header on every POST that creates or charges, and make the behavior contractual: same key plus same payload returns the original result; same key with a different payload returns 422 so the client knows it reused a key by mistake. Store the key, a hash of the request, and the response together, and check-then-act atomically so two simultaneous retries cannot both slip through. Test the race explicitly with parallel requests; idempotency that only works sequentially is decoration. Document the key lifetime so clients know when it is safe to mint a fresh one.

```http
POST /api/v1/charges HTTP/1.1
Idempotency-Key: op_7d3f9a2c
Content-Type: application/json

{"amount": 2500, "currency": "usd"}
# -> 201 Created, charge ch_123

# Network dropped the response; client retries safely
POST /api/v1/charges HTTP/1.1
Idempotency-Key: op_7d3f9a2c
Content-Type: application/json

{"amount": 2500, "currency": "usd"}
# -> 201 Created, same charge ch_123, no duplicate
```

## Common mistakes
- Treating POST retries as safe without idempotency keys, creating duplicate charges on flaky networks.
- Accepting the same key with a different payload silently, applying the wrong operation.
- Letting idempotency records live forever, turning the key store into an unbounded log.

## Checklist
- Do all creating/charging POSTs accept and honor idempotency keys?
- Is key reuse with a changed payload rejected loudly?
- Are concurrent duplicate submissions handled atomically?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
