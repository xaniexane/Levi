---
skill_id: web_rest_versioning
name: REST API Versioning
description: Path, header, and media-type versioning compared, plus rules for evolving an API without breaking clients.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST API Versioning
## Purpose
Change your API over time without stranding existing clients or freezing progress for fear of breaking them.
## Key ideas
- Path versioning (/v1/orders) is the most visible and the easiest to route, cache, and document.
- Header or media-type versioning keeps URLs clean but is invisible in browser bars and harder to debug.
- Only bump the major version for breaking changes; additive changes (new fields, new endpoints) do not need one.
- Never remove or rename a field in a shipped version; deprecate it with a sunset date and keep serving it.
- Publish a deprecation policy: how notice is given, how long old versions live, and what Sunset headers say.

## In practice
Start with /v1 in the path on day one, even when v1 is the only version; adding it later is itself a breaking change. Define breaking precisely for your API: removing a field, changing a type, tightening validation, or altering default behavior all break someone. Support at least two versions during transitions and announce sunsets in three places: docs, a Sunset response header, and direct outreach to heavy users. Track which version each client uses via API keys or user agents; you cannot retire v1 safely if you cannot see who still calls it.

```http
GET /api/v1/orders/42 HTTP/1.1
# -> 200 OK, plus deprecation notice when v1 is aging:
# Sunset: Sat, 01 Jan 2028 00:00:00 GMT
# Deprecation: version="v1", date="2027-01-01"

GET /api/v2/orders/42 HTTP/1.1
# -> current version, same resource, evolved shape
```

## Common mistakes
- Shipping without any version marker, then discovering every change is a breaking change.
- Bumping versions for additive changes, training clients to ignore version numbers.
- Removing deprecated fields on schedule without checking whether major clients migrated.

## Checklist
- Is the version in the path from the first public release?
- Is there a written definition of what counts as breaking?
- Can you measure per-version usage before sunsetting anything?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
