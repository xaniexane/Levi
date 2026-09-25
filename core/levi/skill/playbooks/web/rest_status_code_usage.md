---
skill_id: web_rest_status_code_usage
name: REST Status Code Usage
description: Which status codes to return for creates, updates, deletes, validation failures, and conflicts in a REST API.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Status Code Usage
## Purpose
Standardize the codes your API returns so clients can write one error-handling path that works across every endpoint.
## Key ideas
- POST that creates returns 201 with a Location header pointing at the new resource.
- Successful PUT and PATCH return 200 with the updated representation, or 204 when there is nothing to return.
- DELETE returns 204 on success; returning 200 with a confirmation body is also fine, but be consistent.
- Validation failures are 400 or 422; 409 Conflict is for state clashes like duplicate unique fields or version mismatches.
- 404 means the resource does not exist; never return 404 for a valid resource the caller merely lacks permission to see (use 403).

## In practice
Write the status-code table before you write the handlers, and treat it as a contract. Clients will branch on these codes for years, so changing 400 to 422 later is a breaking change in practice even if the body looks the same. Reserve 500 for bugs you need to fix and 503 for trouble that will pass; when a downstream dependency fails, decide whether it is your bug (500) or a temporary outage (503 or 502) and say so honestly. Log the code class distribution per endpoint: a sudden rise in 4xx on one route usually means a client shipped a bad update, not that your server broke.

```http
POST /api/v1/orders HTTP/1.1
# -> 201 Created, Location: /api/v1/orders/987

PATCH /api/v1/orders/987 HTTP/1.1
# -> 200 OK with updated order, or 409 Conflict on version clash

DELETE /api/v1/orders/987 HTTP/1.1
# -> 204 No Content
```

## Common mistakes
- Returning 200 for validation errors, forcing every client to parse bodies to detect failure.
- Using 404 to hide forbidden resources inconsistently, sometimes 403 and sometimes 404 for the same case.
- Returning 500 for rate limits or maintenance windows, which misdirects on-call engineers.

## Checklist
- Is there a written status-code contract per endpoint, reviewed like an interface?
- Do creates return 201 with Location and deletes return 204?
- Are 4xx and 5xx distinguished by who can fix the problem?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
