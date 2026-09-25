---
skill_id: web_rest_error_responses
name: REST Error Responses
description: Design one consistent error body shape with codes, messages, and field-level details clients can act on.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Error Responses
## Purpose
Make failures as programmable as successes: one shape, machine-readable codes, and human-readable guidance.
## Key ideas
- Every error response shares one envelope: a stable machine code, a human message, and optional details.
- Machine codes (ORDER_LIMIT_EXCEEDED) stay stable across versions; human messages may be reworded freely.
- Field-level validation errors name the field, the rejected value's problem, and how to fix it.
- Include a request or trace id so support can find the exact log lines for a client's failure.
- Never change the envelope shape between endpoints; clients write one parser and reuse it everywhere.

## In practice
Treat your error format as public API from day one, because the moment a client switches on your error.code, it is. Keep a registry of machine codes with their meaning and the HTTP status each pairs with; review additions the way you review new endpoints. Messages should tell the caller what to do next, not just what went wrong: 'qty must be between 1 and 99' beats 'invalid qty'. In production, strip stack traces and internal paths from error bodies; keep those in server logs keyed by the trace id you returned to the client.

```json
{
  "error": {
    "code": "ORDER_LIMIT_EXCEEDED",
    "message": "An order may contain at most 50 items; split into multiple orders.",
    "trace_id": "req_9f2c7a1e",
    "details": [
      {"field": "items", "issue": "too_many", "limit": 50}
    ]
  }
}
```

## Common mistakes
- A different error shape per endpoint, forcing clients to write a parser per route.
- Putting the only useful information in a free-text message that clients must string-match.
- Leaking stack traces, SQL, or file paths in production error bodies.

## Checklist
- Is there one documented error envelope used by every endpoint?
- Do machine codes stay stable while messages stay human?
- Does every error carry a trace id for log correlation?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
