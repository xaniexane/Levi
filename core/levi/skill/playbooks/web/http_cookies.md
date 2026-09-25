---
skill_id: web_http_cookies
name: HTTP Cookies
description: How cookies work: Set-Cookie attributes, the cookie jar, and the flags that keep session cookies safer.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals, security]
version: 1.0.0
---
# HTTP Cookies
## Purpose
Understand the mechanism behind sessions and personalization, and the attributes that separate a careful cookie from a careless one.
## Key ideas
- The server sends Set-Cookie headers; the browser stores them in a cookie jar and returns matching ones on future requests.
- Domain and Path scope where a cookie is sent; narrower scope means less exposure.
- HttpOnly blocks JavaScript from reading the cookie, closing the simplest theft path for session tokens.
- Secure requires HTTPS transport, and SameSite controls whether the cookie rides along on cross-site requests.
- Expires or Max-Age sets lifetime; session cookies without them die when the browser closes.

## In practice
Treat cookies as small, visible, user-editable storage: never put anything in one that must stay secret or trustworthy, because the client can read and rewrite every byte. Session cookies should be random, unguessable identifiers that point at server-side state, not the state itself. Set HttpOnly, Secure, and SameSite=Lax as your default trio, scope Domain and Path as tightly as the app allows, and give cookies the shortest lifetime the user experience tolerates. When a session misbehaves, the browser's storage inspector plus the raw Set-Cookie headers will show you exactly what was set, what was sent, and what was dropped.

```http
HTTP/1.1 200 OK
Set-Cookie: session=9f2c7a1e4b6d; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600
Set-Cookie: theme=dark; Path=/; SameSite=Lax; Max-Age=31536000

# Later request: the browser returns matching cookies
GET /dashboard HTTP/1.1
Host: app.example.com
Cookie: session=9f2c7a1e4b6d; theme=dark
```

## Common mistakes
- Storing user roles or permissions in the cookie itself, letting anyone with a text editor promote themselves to admin.
- Omitting SameSite, leaving the cookie attached to cross-site requests and the session exposed to CSRF.
- Using predictable session values like incrementing numbers or usernames instead of random tokens.

## Checklist
- Do session cookies carry only a random identifier, with state kept server-side?
- Are HttpOnly, Secure, and SameSite set on every sensitive cookie?
- Is cookie scope (Domain, Path) as narrow as the app permits?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
