---
skill_id: web_js_fetch_api
name: JavaScript Fetch API
description: Make HTTP requests with fetch: options, reading bodies, and handling the errors fetch does not throw.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend, http]
version: 1.0.0
---
# JavaScript Fetch API
## Purpose
Call APIs correctly: set methods and headers, read responses, and treat HTTP errors as errors.
## Key ideas
- fetch returns a promise of a Response; it only rejects on network failure, not on HTTP error statuses.
- Always check response.ok (or the status) before parsing; a 404 still resolves the promise.
- Response bodies are read once via .json(), .text(), or .blob(); pick the reader that matches Content-Type.
- Request options carry method, headers, and body; stringify JSON bodies and set Content-Type yourself.
- AbortController cancels in-flight requests, essential for typeahead and unmounted components.

## In practice
Wrap fetch in a small helper that checks response.ok and throws a rich error (status, url, parsed body) so every call site gets error handling for free. Set Content-Type: application/json whenever you send a JSON body, and JSON.stringify the payload; fetch will not do either for you. For search-as-you-type, keep one AbortController per input and abort the previous request before starting the next, so slow responses cannot overwrite fresh ones. Time out long requests with AbortSignal.timeout where supported; a request that hangs forever is worse than one that fails fast.

```javascript
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${detail}`);
  }
  return res.status === 204 ? null : res.json();
}
```

## Common mistakes
- Assuming fetch throws on 404/500 and skipping the response.ok check.
- Forgetting Content-Type on JSON POSTs, so the server cannot parse the body.
- Letting stale typeahead responses overwrite newer results for lack of aborting.

## Checklist
- Does your fetch wrapper check response.ok and throw informative errors?
- Are JSON bodies stringified with an explicit Content-Type?
- Are superseded requests aborted instead of racing?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
