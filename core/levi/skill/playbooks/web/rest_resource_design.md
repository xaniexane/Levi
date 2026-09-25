---
skill_id: web_rest_resource_design
name: REST Resource Design
description: Model your API as nouns and relationships: collections, members, and sub-resources instead of verbs in URLs.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST Resource Design
## Purpose
Give your API a shape that reads like a map of things rather than a list of remote procedure calls, so URLs stay stable as behavior grows.
## Key ideas
- Resources are nouns: /orders, /orders/42, /orders/42/items. Verbs belong in HTTP methods, not in paths.
- A collection (/orders) and its members (/orders/42) are different resources with different methods allowed.
- Sub-resources express ownership: /users/42/orders only makes sense when orders belong to that user.
- Use plural nouns for collections and keep naming consistent; mixing /order and /orders breeds confusion.
- Actions that do not fit CRUD (cancel, approve) can be sub-resources like /orders/42/cancellation or a PATCH on a status field.

## In practice
Start every design by listing the nouns your users care about, then draw the containment lines between them. If you cannot say it as a noun phrase, it is probably an action hiding inside a URL, and it deserves either a method or a purpose-built sub-resource. Keep identifiers opaque where you can: sequential integers leak growth rates and invite enumeration, while random or UUID-style ids reveal nothing. A good resource model survives feature after feature because new behavior hangs off new sub-resources instead of rewriting old URLs.

```http
GET    /api/v1/orders          # list (collection)
POST   /api/v1/orders          # create (collection)
GET    /api/v1/orders/42       # read one (member)
PATCH  /api/v1/orders/42       # partial update (member)
DELETE /api/v1/orders/42       # remove (member)
GET    /api/v1/orders/42/items # sub-resource: items of order 42
POST   /api/v1/orders/42/cancellation  # action as sub-resource
```

## Common mistakes
- Verb-laden URLs like /getOrders or /createUser, which duplicate what the HTTP method already says.
- Deep nesting (/a/1/b/2/c/3/d) that couples resources which could be addressed flatly with filters.
- Exposing sequential database ids that leak business metrics and make enumeration trivial.

## Checklist
- Can every URL be read aloud as a noun phrase?
- Is nesting limited to genuine ownership, two levels at most?
- Are identifiers opaque rather than sequential where enumeration matters?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
