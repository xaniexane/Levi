---
skill_id: web_rest_pagination
name: REST Pagination
description: Offset, page-number, and cursor pagination: how each works, where each breaks, and what to expose to clients.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Pagination
## Purpose
Keep list endpoints fast and correct as collections grow from dozens to millions of records.
## Key ideas
- Offset pagination (?offset=40&limit=20) is simple but skips or duplicates rows when data changes between pages.
- Page-number pagination has the same drift problem and gets slow on deep pages in most databases.
- Cursor pagination (an opaque token pointing at the last seen row) stays correct under inserts and is fast with an index.
- Always cap page size server-side; never let the client request a million rows in one call.
- Return pagination metadata (next cursor, total count where cheap) so clients do not have to guess.

## In practice
Default to cursor pagination for anything user-facing or unbounded: encode the sort key and row id into an opaque token, and never let clients construct cursors by hand. Keep offset pagination only for small, stable, admin-style lists where its simplicity outweighs its drift. Whatever you choose, enforce a maximum page size (50 or 100 is a sane default) and document the default size, because clients will rely on it. Include a next link or cursor in every paged response; making clients build the next URL from documentation is how off-by-one bugs are born.

```http
GET /api/v1/orders?limit=20 HTTP/1.1

HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": [ {"id": 101}, {"id": 102} ],
  "paging": {
    "next_cursor": "eyJpZCI6MTAyfQ==",
    "has_more": true
  }
}

GET /api/v1/orders?limit=20&cursor=eyJpZCI6MTAyfQ== HTTP/1.1
```

## Common mistakes
- Allowing unbounded page sizes, handing any client a denial-of-service button labeled limit=1000000.
- Using offset pagination on a feed that updates constantly, so users see duplicates and gaps.
- Exposing raw database offsets in cursors, leaking internals and inviting tampering.

## Checklist
- Is page size capped server-side with a documented default?
- Do high-churn lists use cursor pagination instead of offset?
- Are cursors opaque tokens, not raw database internals?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
