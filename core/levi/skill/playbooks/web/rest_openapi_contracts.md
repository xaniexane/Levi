---
skill_id: web_rest_openapi_contracts
name: REST OpenAPI Contracts
description: Describe your API with OpenAPI: what to document, how to keep the spec honest, and what it buys you.
risk: info
permissions: []
requires_confirmation: false
tags: [http, api, rest]
version: 1.0.0
---
# REST OpenAPI Contracts
## Purpose
Turn your API from folklore into a machine-readable contract that powers docs, clients, mocks, and tests.
## Key ideas
- OpenAPI describes paths, operations, parameters, request/response schemas, and security schemes in one document.
- The spec is the contract: generate documentation, client SDKs, and mock servers from it instead of hand-writing each.
- Validate in both directions: requests against the spec in tests, and the spec against the implementation in CI.
- Keep examples in the spec; they become the documentation's illustrations and the test suite's fixtures.
- A stale spec is worse than none, because it teaches clients lies with authority.

## In practice
Write the spec alongside the endpoint, in the same pull request, and make CI fail when they drift: contract tests that replay examples against the running server catch most lies. Start strict on required fields and enums, because loosening later is backward compatible while tightening is not. Publish the spec at a stable URL (/openapi.json) so tooling can consume it, and version it with the API itself. When the spec and the code disagree, fix the code if clients depend on the spec, and fix the spec if it was aspirational; either way, decide explicitly and record the decision.

```yaml
openapi: 3.1.0
info:
  title: Orders API
  version: 1.4.0
paths:
  /orders/{id}:
    get:
      parameters:
        - name: id
          in: path
          required: true
          schema: {type: integer}
      responses:
        '200':
          description: The order
          content:
            application/json:
              schema: {$ref: '#/components/schemas/Order'}
```

## Common mistakes
- Writing the spec once at launch and never updating it, so it describes an API that no longer exists.
- Documenting aspirational behavior the server does not implement, then blaming clients for trusting it.
- Skipping examples, leaving consumers to guess shapes from schema fragments.

## Checklist
- Does CI verify the spec matches the running implementation?
- Is the spec versioned and published at a stable URL?
- Do all operations include realistic examples?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
