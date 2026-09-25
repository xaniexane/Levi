---
skill_id: web_rest_filtering_sorting
name: REST Filtering and Sorting
description: Design query parameters for filtering, sorting, and field selection that stay predictable and safe.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Filtering and Sorting
## Purpose
Let clients slice collections without you building a custom endpoint for every combination they dream up.
## Key ideas
- Filters are query parameters naming fields: ?status=shipped&region=west; keep the vocabulary tied to resource fields.
- Sorting uses a sort parameter with - for descending: ?sort=-created_at; whitelist sortable fields.
- Field selection (?fields=id,name,total) trims payloads for bandwidth-sensitive clients.
- Range filters need explicit operators: ?created_after=2026-01-01 reads better than overloading the field name.
- Every filter and sort must map to an indexed query path, or one creative client can pin your database.

## In practice
Publish the exact set of supported filters per endpoint and reject unknown ones with a 400 rather than silently ignoring them; silent ignores make clients believe a filter worked when it did not. Whitelist sortable fields and cap the number of sort keys, because sorting by an unindexed column on a million-row table is a slow query wearing a trench coat. For field selection, validate requested fields against the schema so ?fields=password_hash fails loudly. Log the most-used filter combinations; they are your index-design roadmap and your cache-key candidates.

```http
GET /api/v1/orders?status=shipped&region=west&sort=-created_at&fields=id,total,created_at&limit=20 HTTP/1.1

# Server rejects unknown filters loudly
GET /api/v1/orders?bogus=1 HTTP/1.1
# -> 400 Bad Request
{"errors": [{"param": "bogus", "message": "unknown filter"}]}
```

## Common mistakes
- Silently ignoring unknown query parameters, so clients think filters apply when they do not.
- Allowing sort on any field including unindexed ones, creating unpredictable slow queries.
- Passing filter values straight into query strings without validation, opening injection paths.

## Checklist
- Is the supported filter/sort vocabulary documented and enforced per endpoint?
- Do unknown parameters produce 400 instead of being ignored?
- Does every filter/sort combination hit an indexed query plan?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
