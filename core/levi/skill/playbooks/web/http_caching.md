---
skill_id: web_http_caching
name: HTTP Caching
description: Freshness, validation, and invalidation: how Cache-Control, ETag, and conditional requests keep the web fast.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals, performance]
version: 1.0.0
---
# HTTP Caching
## Purpose
Make caching a deliberate design choice: know when a response may be reused, how clients revalidate, and what to do when content changes.
## Key ideas
- Freshness says a cached copy may be reused without asking: Cache-Control: max-age=3600 lets a cache serve it for an hour.
- Validation says the cache must check first: ETag or Last-Modified let the server answer 304 Not Modified instead of resending the body.
- no-store forbids caching entirely (sensitive data); no-cache allows storage but requires revalidation every time.
- Conditional requests (If-None-Match, If-Modified-Since) turn a full download into a cheap freshness check.
- Invalidation is the hard part: versioned URLs or content hashes beat trying to purge caches by path.

## In practice
Cache with intent by classifying each response: immutable assets (hashed filenames) get long max-age plus immutable; frequently-read, slowly-changing data gets a short max-age with ETag validation; per-user or sensitive responses get no-store. The classic failure is caching something personal with a shared cache, so always pair private data with Cache-Control: private or no-store. When content must change immediately, do not rely on purging; ship a new URL (app.a1b2c3.js) so old cached copies simply stop being referenced. A quick check of response headers in the browser devtools network panel tells you in seconds whether a stale-content complaint is a caching problem.

```http
# Immutable asset: cache for a year, never revalidate
HTTP/1.1 200 OK
Cache-Control: public, max-age=31536000, immutable
Content-Type: text/javascript

# Personal data: never stored by shared caches
HTTP/1.1 200 OK
Cache-Control: private, no-store
Content-Type: application/json
```

## Common mistakes
- Caching authenticated or personalized responses in a shared cache, leaking one user's data to another.
- Using long max-age on unversioned URLs, then discovering you cannot push an urgent fix past the cache.
- Forgetting that no-cache does not mean do-not-store; it means revalidate, which surprises people during outages.

## Checklist
- Is every cacheable response classified as immutable, revalidatable, or private?
- Do asset URLs contain content hashes so updates bypass old caches?
- Are sensitive responses marked no-store or private?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
