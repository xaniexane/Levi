# Share-card injection: hermetic by default

**Decision (2026-09-15).** `injectGrokPwaHead` and `createHeadInjector` in
`scripts/grok-pwa-shared.mjs` are hermetic: without an explicit `ctx.cwd`
they use exactly the context they are given and never read ambient workspace
state (`src/lib/og/site.json`, `public/og.jpg`), even when such files exist
under `process.cwd()`.

**Why.** The old code fell back to `snapshotOgIdentity(process.cwd())` and a
`public/og.jpg` check whenever the caller omitted `cwd`/`site`. In practice
that meant running the unit tests from `web/` silently injected this
workspace's real branding (`site.json` → `{"title": "LEVI", "card": "custom"}`)
into every hermetic test case — 8 test failures — and, worse, made injection
output depend on which directory the caller happened to run from. One
workspace's branding must never leak into another app's share card.

**What changed.**

- `normalizeHeadContext`: workspace discovery (`snapshotOgIdentity`,
  `applyCustomCardFromFs`) runs only when `ctx.cwd` is explicitly provided.
  Otherwise `site` defaults to `{}` — no filesystem reads at all.
- `ogCardPublicPath`: an explicitly empty `cwd` returns `""` instead of
  resolving a relative path against `process.cwd()`.
- Callers that need discovery pass it explicitly:
  - Vite plugin (`scripts/grok-pwa-plugin.mjs`) passes `cwd: root` →
    dev/preview behavior unchanged (still discovers `site.json` + `og.jpg`).
  - Nitro middleware (`server/middleware/grok-pwa.ts`) passes a baked `site`
    and no `cwd` → deployed behavior unchanged.

**Title precedence (unchanged, encoded in `resolveOgTitle` and asserted by
`scripts/grok-pwa-plugin.test.mjs`):**

1. baked/explicit `site.title`
2. the document's own `<title>`
3. the published `*.grok.me` host slug (e.g. `wild-race.grok.me` → "Wild Race")
4. the `appName` argument (default `"Grok App"`)

**Reversibility.** If a future caller needs the old ambient fallback, pass
`cwd: process.cwd()` explicitly — the discovery helpers are unchanged. The
decision removes an implicit default, not a capability.
