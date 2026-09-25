---
skill_id: sys_net_http_basics
name: Networking HTTP Basics
description: The web's protocol: requests, responses, methods, status codes, and headers.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, web]
version: 1.0.0
---
# Networking HTTP Basics

## Purpose

The web's protocol: requests, responses, methods, status codes, and headers.

## Overview

HTTP is a request/response protocol over (usually) TCP/TLS. The client sends a method, path, version, headers, and optional body; the server replies with a status line, headers, and body. Methods: GET (retrieve, no body semantics), POST (submit/process), PUT (replace), PATCH (partial update), DELETE (remove), HEAD (headers only). Safe methods (GET/HEAD) must not change state; idempotent ones (PUT/DELETE) give the same result repeated - design APIs accordingly. Status codes: 2xx success (200 OK, 201 Created, 204 No Content), 3xx redirection (301/302, 304 Not Modified), 4xx client error (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Too Many Requests), 5xx server error (500, 502 Bad Gateway, 503 Unavailable). Key headers: Content-Type/Length, Authorization, Cache-Control, Location, Set-Cookie. HTTP/1.1 is textual with keep-alive; HTTP/2 multiplexes binary frames over one connection; HTTP/3 runs over QUIC/UDP. Statelessness: each request stands alone - sessions ride on cookies or tokens. Caching (ETag/Last-Modified, Cache-Control) and conditional requests cut load massively. Debugging: curl -i shows the raw exchange; -v shows the TLS handshake too. Security: validate and bound everything from clients; never trust headers like X-Forwarded-For for auth decisions.

## Quick reference

- Methods: GET retrieve, POST submit, PUT replace, PATCH partial, DELETE remove.

- 2xx success, 3xx redirect, 4xx client error, 5xx server error.

- GET/HEAD must be safe; PUT/DELETE should be idempotent.

- HTTP/1.1 textual; HTTP/2 multiplexed; HTTP/3 over QUIC.

- Stateless: sessions via cookies/tokens. Cache with ETag/Cache-Control.

- curl -i: raw exchange. Validate/bound all client input.


## Worked example

Reading the raw HTTP exchange:

```
# Full request/response, headers included:
curl -i https://example.com/ | head -20

# POST with a JSON body:
curl -sS -X POST https://httpbin.org/post \
  -H 'Content-Type: application/json' \
  -d '{"name": "ada"}' | head -c 300

# Python stdlib client:
import json, urllib.request
req = urllib.request.Request(
    'https://httpbin.org/post',
    data=json.dumps({'name': 'ada'}).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, timeout=10) as r:
    print(r.status, r.headers.get('Content-Type'))
```

- -i prints response headers: status line, content type, caching.

- POST with explicit Content-Type; -d sends the body.

- urlopen with timeout: stdlib HTTP without hanging forever.


## Common mistakes

- State-changing GETs: crawlers and retries corrupt data.
  Fix: GET/HEAD must be safe; mutations go in POST/PUT/PATCH/DELETE.

- Ignoring status codes: treating every 200-shaped response as success.
  Fix: Check status first; 4xx/5xx carry the real story in the body.


## Quick checks

Q: PUT vs PATCH - which for updates?
A: PUT replaces the whole resource (idempotent, send the full new state). PATCH applies a partial change (send only diffs). Use PUT when the client holds the full representation, PATCH for targeted edits.


Q: Why did my GET request change server state? (It shouldn't.)
A: Someone made GET non-safe. Crawlers, prefetchers, and retries hit GETs freely - state changes belong in POST/PUT/PATCH/DELETE so infrastructure can treat GET as repeatable.


## Mental model

HTTP is a restaurant: the menu (API docs) lists dishes (paths), you order with a method (GET = 'show me', POST = 'make this'), the kitchen replies with a status (200 = 'here you go', 404 = 'we don't serve that', 500 = 'kitchen fire'). The waiter remembers nothing between visits (stateless) - your loyalty card (cookie) identifies you.
