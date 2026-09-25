---
skill_id: web_rest_rate_limiting
name: REST Rate Limiting
description: Design fair rate limits: quotas, windows, headers, and the 429 responses that keep clients informed.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Rate Limiting
## Purpose
Protect shared infrastructure from accidental and deliberate overload while giving legitimate clients a predictable budget.
## Key ideas
- Limits are usually expressed per key or per IP per window: 1000 requests per hour, 10 per second burst.
- Fixed windows are simple; sliding windows and token buckets smooth bursts more fairly.
- Communicate the budget with RateLimit-Limit, RateLimit-Remaining, and RateLimit-Reset headers on every response.
- Exceeding the budget returns 429 Too Many Requests with Retry-After telling the client how long to wait.
- Different endpoints deserve different budgets: cheap reads can be generous, expensive writes should be strict.

## In practice
Set limits from measured capacity, not round numbers: load-test the endpoint, decide what fraction one client may consume, and set the limit there. Return the rate-limit headers on success too, not just on 429, so well-behaved clients can pace themselves before hitting the wall. Use per-key limits for authenticated APIs and per-IP only as a backstop, since IPs are shared by NAT and punished unfairly. When a client is persistently over budget, that is a conversation (raise their tier) or an abuse signal, not just a bigger hammer; log the pattern before blocking.

```http
HTTP/1.1 200 OK
RateLimit-Limit: 1000
RateLimit-Remaining: 873
RateLimit-Reset: 3600
Content-Type: application/json

HTTP/1.1 429 Too Many Requests
Retry-After: 42
RateLimit-Reset: 42

{"error": {"code": "RATE_LIMITED", "message": "Slow down; retry in 42 seconds."}}
```

## Common mistakes
- Returning 429 without Retry-After, leaving clients to guess and hammer the endpoint.
- Limiting by IP on an authenticated API, punishing everyone behind one office NAT for one bad script.
- Setting one global limit for endpoints with wildly different costs, starving cheap reads or permitting write floods.

## Checklist
- Are limits derived from measured capacity per endpoint cost?
- Do all responses carry the remaining-budget headers?
- Does every 429 include Retry-After?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
