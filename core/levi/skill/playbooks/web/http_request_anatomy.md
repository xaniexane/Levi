---
skill_id: web_http_request_anatomy
name: HTTP Request Anatomy
description: Dissect the parts of an HTTP request: request line, headers, and body, and what each part tells the server.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Request Anatomy
## Purpose
Give you a reliable mental model of what a client actually sends over the wire when it makes an HTTP request, so debugging, logging, and API design all rest on the same foundation.
## Key ideas
- Every request starts with a request line: METHOD, path, and HTTP version, e.g. GET /users/42 HTTP/1.1.
- Headers are key-value metadata lines that follow the request line; they describe the client, what it accepts, and how the body is encoded.
- An empty line separates headers from the optional message body, which carries payload data on POST, PUT, and PATCH.
- The query string lives on the request line after a ? and is for filtering or identifying; the body is for submitting new data.
- Method plus path is the identity of the operation; two requests with the same method and path should mean the same thing.

## In practice
When a request misbehaves, read it bottom-up like a letter: the request line is the address, headers are the envelope notes, and the body is the letter itself. Most API bugs are envelope bugs: a missing Content-Type that makes the server guess at the body format, or an Accept header that asks for XML while the client only parses JSON. Logging the full request line plus a handful of headers (Host, User-Agent, Content-Type, Content-Length, Authorization presence but never its value) is usually enough to diagnose routing and parsing failures without storing anything sensitive.

```http
POST /api/orders HTTP/1.1
Host: shop.example.com
Content-Type: application/json
Content-Length: 57
Accept: application/json

{"item": "notebook", "qty": 2, "ship": "standard"}
```

## Common mistakes
- Putting secrets or large payloads in the query string, where they land in logs, browser history, and referer headers.
- Sending a body with a GET request and relying on the server to read it; many servers and proxies ignore GET bodies.
- Forgetting Content-Type on POST/PUT, leaving the server to guess whether the body is JSON, form data, or something else.

## Checklist
- Can you name the three parts of any raw request you are debugging?
- Does your logging capture method, path, and key headers without recording credentials?
- Is every request body labeled with an explicit Content-Type?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
