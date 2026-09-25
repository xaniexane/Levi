---
skill_id: web_http_status_codes
name: HTTP Status Codes
description: A practical tour of the status code classes 1xx through 5xx and the codes you will actually use every day.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Status Codes
## Purpose
Turn status codes from memorized trivia into a decision tool: pick the code that tells the client exactly what happened and what to do next.
## Key ideas
- 1xx is informational, 2xx means success, 3xx means go look elsewhere, 4xx means the client messed up, 5xx means the server did.
- 200 OK, 201 Created, and 204 No Content cover nearly all success cases; reach for 201 when you made something new.
- 400 Bad Request is for malformed input, 401 Unauthorized means missing or bad credentials, 403 Forbidden means valid credentials but no permission, 404 Not Found means the resource is not there.
- 301 and 308 are permanent redirects, 302 and 307 temporary; 307 and 308 preserve the method while 301 and 302 historically may not.
- 429 Too Many Requests and 503 Service Unavailable both tell the client to back off; pair them with Retry-After.

## In practice
Choose codes the way a traffic light chooses colors: the class must be right even if the exact code is debatable. A validation failure is 400 or 422, never 200 with an error flag. An expired session is 401, a permission problem is 403; mixing them up sends users down the wrong recovery path, re-logging-in when they actually need an admin. For server failures use 500 for genuine bugs and 503 when the service is temporarily unable, so load balancers and clients know the difference between call-an-engineer and try-again-later. Keep a short table of your API's codes in its documentation and it will save hundreds of support questions.

```http
# Validation failed: the client sent bad data
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"errors": [{"field": "email", "message": "not a valid address"}]}

# Rate limited: back off and try later
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{"error": "quota exceeded, retry in 60 seconds"}
```

## Common mistakes
- Returning 200 with {success: false} in the body, which defeats HTTP-aware tooling from caches to alerting.
- Using 500 for client-caused problems like bad input, which pages engineers for something no deploy can fix.
- Confusing 401 (who are you) with 403 (I know who you are, and no), misleading users about the fix.

## Checklist
- Does the code class (2xx/4xx/5xx) always match who is at fault?
- Are 401 and 403 used distinctly and documented?
- Do 429 and 503 responses include a Retry-After header?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
