---
skill_id: web_js_storage_apis
name: JavaScript Storage APIs
description: localStorage, sessionStorage, and IndexedDB: what to store where, limits, and the security caveats.
risk: info
permissions: []
requires_confirmation: false
tags: [javascript, frontend]
version: 1.0.0
---
# JavaScript Storage APIs
## Purpose
Persist client-side data in the right store with eyes open about capacity, lifetime, and exposure.
## Key ideas
- localStorage persists across sessions on one origin (~5MB); sessionStorage dies with the tab.
- Both store strings only; JSON.stringify on the way in, JSON.parse on the way out.
- Storage is synchronous and blocks the main thread; keep values small and access infrequent.
- Any JavaScript on the page can read storage, so never put secrets or sensitive PII there.
- IndexedDB is the async, larger, structured option for real client-side datasets.

## In practice
Use storage for preferences and caches (theme, drafts, last-viewed), never for tokens or personal data; an XSS hole turns localStorage into a credential leak, while HttpOnly cookies stay out of JavaScript's reach. Wrap access in try/catch because private browsing and quotas make setItem throw, and your app should degrade rather than crash. Namespace your keys (app.theme, app.draft) and version stored shapes so format changes do not resurrect ancient data. For anything bigger than settings, reach for IndexedDB with a small promise wrapper instead of cramming megabytes into a synchronous string store.

```javascript
const store = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem("app." + key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem("app." + key, JSON.stringify(value)); }
    catch { /* quota or private mode: degrade silently */ }
  }
};
store.set("theme", "dark");
```

## Common mistakes
- Storing auth tokens in localStorage, exposing them to any injected script.
- Assuming setItem always succeeds and crashing in private browsing or full quotas.
- Changing stored data shapes without versioning, then choking on old entries.

## Checklist
- Are secrets and sensitive PII absent from all client storage?
- Is storage access wrapped against quota and private-mode failures?
- Are stored shapes versioned and namespaced?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
