---
skill_id: web_http_response_anatomy
name: HTTP Response Anatomy
description: Break down the status line, response headers, and body, and learn what each part signals to the client.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Response Anatomy
## Purpose
Make responses legible: once you can read a status line, a few headers, and a body the way you read a request, half of all web debugging becomes mechanical.
## Key ideas
- The status line carries the HTTP version, a three-digit status code, and a short reason phrase like 200 OK.
- The status code is the machine-readable verdict; the reason phrase is decorative and clients should not depend on it.
- Response headers describe the body (Content-Type, Content-Length), caching rules, and security policy.
- The body is optional and its meaning is defined by Content-Type: JSON, HTML, an image, or nothing at all for 204.
- A response is only as trustworthy as its headers; a 200 with Content-Type text/html containing an error page is still a failure from the client's view.

## In practice
Treat the status code as the first word of the answer and the headers as the fine print. When a client reports a strange failure, check the status code before reading the body: a 200 with an error message inside means the server lied politely, a 404 with HTML means the client asked for the wrong path, and a 500 with no body means the server died before it could explain itself. Your own APIs should return codes that match reality, put machine-readable error details in a consistent body shape, and set Content-Type honestly so clients never have to sniff the payload to figure out what it is.

```http
HTTP/1.1 201 Created
Content-Type: application/json
Content-Length: 48
Location: /api/orders/987

{"id": 987, "status": "received"}
```

## Common mistakes
- Returning 200 for every outcome and burying the real result in the body, which breaks caches, retries, and monitoring.
- Omitting Content-Type so clients guess the format and occasionally guess wrong.
- Leaking stack traces or internal paths in error bodies sent to untrusted clients.

## Checklist
- Does each endpoint return the status code that matches what actually happened?
- Is Content-Type set correctly on every response, including errors?
- Do error bodies use one consistent shape across the whole API?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
