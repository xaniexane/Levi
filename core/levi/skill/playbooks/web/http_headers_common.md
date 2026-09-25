---
skill_id: web_http_headers_common
name: Common HTTP Headers
description: The everyday headers that control content type, authentication, caching, and negotiation, and how to read them.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# Common HTTP Headers
## Purpose
Build fluency in the twenty or so headers that appear in nearly every request and response, so raw traffic stops looking like noise.
## Key ideas
- Host identifies which virtual site the client wants; without it one server cannot serve many domains on one IP.
- Content-Type declares the body's media type and charset, e.g. application/json; charset=utf-8; Content-Length gives its byte size.
- Accept and Accept-Language let the client state its preferences; the server answers with Content-Type and Content-Language.
- Authorization carries credentials (usually a Bearer token); never log its value, only its presence and scheme.
- Cache-Control, ETag, and Last-Modified drive conditional requests and freshness; Location points at redirects and new resources.

## In practice
Learn headers in functional groups rather than as a flat list: identity (Host, User-Agent), content description (Content-Type, Content-Length, Content-Encoding), negotiation (Accept-*), state (Cookie, Set-Cookie), caching (Cache-Control, ETag, If-None-Match), and control (Authorization, Location, Retry-After). When debugging, scan one group at a time. A garbled response is usually a content-description problem. A stale page is a caching problem. An auth failure is an Authorization or Cookie problem. Naming the group first narrows the search to a handful of lines.

```http
GET /feed HTTP/1.1
Host: news.example.com
Accept: application/json
Accept-Language: en-US,en;q=0.9
If-None-Match: "v3-abc"
Cookie: session=xyz789

HTTP/1.1 304 Not Modified
ETag: "v3-abc"
Cache-Control: max-age=300
```

## Common mistakes
- Trusting client-sent headers like X-Forwarded-For or User-Agent for security decisions; they are trivially forged.
- Logging the Authorization header value into application logs, turning every log store into a credential store.
- Setting conflicting caching headers, such as no-store alongside a long max-age, and getting unpredictable behavior.

## Checklist
- Can you group any header you meet into identity, content, negotiation, state, caching, or control?
- Are credential-bearing headers redacted in all logs?
- Do responses set Content-Type explicitly instead of relying on sniffing?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
