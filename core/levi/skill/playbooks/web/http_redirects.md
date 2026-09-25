---
skill_id: web_http_redirects
name: HTTP Redirects
description: The 3xx family in practice: which code preserves the method, which are permanent, and how redirect chains behave.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Redirects
## Purpose
Use redirects precisely: pick the code that says what you mean about permanence and method preservation, and keep chains short.
## Key ideas
- 301 Moved Permanently and 308 Permanent Redirect are cacheable and signal a lasting move; use them for canonical URLs.
- 302 Found and 307 Temporary Redirect signal a short-term detour, such as post-login landing pages.
- 307 and 308 guarantee the method and body are preserved; 301 and 302 historically allowed clients to switch POST to GET.
- The Location header carries the new URL, which may be relative; clients resolve it against the original request.
- Every hop in a redirect chain costs a round trip and each hop is a place where headers or method can be lost.

## In practice
Reach for 308 when a resource has moved for good and the method matters (API version moves, POST endpoints), and 307 for temporary method-preserving detours. Use 301 for permanent page moves where the old POST-to-GET rewrite behavior is harmless or even desired, and 302 for the classic login-then-bounce flow. Keep chains to one hop wherever possible: redirect /old straight to /final, not /old to /middle to /final, because each hop adds latency and multiplies the chance a client drops the Authorization header or downgrades HTTPS. Audit your redirects periodically; chains accrete silently as pages move again and again.

```http
# Permanent, method-preserving move of an API endpoint
HTTP/1.1 308 Permanent Redirect
Location: /api/v2/orders

# Temporary detour after login
HTTP/1.1 302 Found
Location: /dashboard
```

## Common mistakes
- Using 302 for permanent moves, so search engines and clients never learn the new canonical URL.
- Building long redirect chains that add seconds of latency and drop headers along the way.
- Redirecting POST endpoints with 301/302 and being surprised when clients resend as GET.

## Checklist
- Does each redirect use the code that matches its permanence and method needs?
- Are chains collapsed to a single hop where possible?
- Do redirects preserve HTTPS and avoid leaking sensitive headers?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
