# LEVI Hosting — two paths, honestly labeled

LEVI's web surfaces can leave the builder platform they were born on.
Two tracks, different purity:

| | `levi serve` (pure) | GitHub Pages (pragmatic) |
|---|---|---|
| Cost | free (your hardware) | free (public repo) |
| Platform dependency | none — stdlib Python | GitHub's platform |
| "Created with Grok" pill | never injected | never injected (`LEVI_SELFHOST=1`) |
| Self-reliant | yes, fully | no — convenient free tier |

## Track 1 — `levi serve`: LEVI-native static server (pure)

`core/levi/serve/` is stdlib-only (`http.server.ThreadingHTTPServer`):

```
levi serve --dir web/.vercel/output/static --port 8742
python -m levi.serve --dir web/.vercel/output/static --port 8742
```

- SPA fallback: unknown routes serve `index.html`; missing *assets*
  (`/app.js`, `/x.png`) 404 honestly instead of returning HTML.
- Correct MIME types (`.js`, `.wasm`, `.webmanifest`, …), no directory
  listing ever, request log to stderr.
- Localhost-first: default bind is `127.0.0.1` (Forge-style). `--bind`
  accepts anything else but prints an honest warning — exposing files to
  a network is your explicit choice.

Build the pill-free bundle first. The SSR build emits no `index.html`
(the shell is rendered per request), so `scripts/static-shim.mjs`
generates one from the build's own manifest for pure-static hosts:

```
cd web && LEVI_SELFHOST=1 npm run build && node scripts/static-shim.mjs
levi serve --dir web/.vercel/output/static --port 8742
```

Why the pill is gone: the "Created with Grok / Remix" pill is injected by
`grokPwaPlugin()` (build time) and `server/middleware/grok-pwa.ts` (serve
time). On LEVI's own build and server, neither runs — there is nothing to
strip, the injector simply never exists.

## Track 2 — GitHub Pages (free, pragmatic)

`.github/workflows/pages.yml` builds `web/` on every push to `main` and
deploys to Pages with the official `actions/upload-pages-artifact` +
`actions/deploy-pages` actions:

- `npm ci`, then `LEVI_SELFHOST=1 node scripts/with-app-env.mjs vite build --base=/Levi/`
  (invoked via the wrapper so `--base` reaches vite — npm arg-forwarding would
  misdeliver it to `db:migrate`), then `node scripts/static-shim.mjs`
- `.vercel/output/static/index.html` → `404.html` (the Pages SPA-fallback trick)
- Permissions: `pages: write`, `id-token: write`; concurrency group `pages`

Free because this repo is public. Custom domain optional later
(repo Settings → Pages). Enable Pages once under Settings → Pages
(source: GitHub Actions).

Honest note: Pages is GitHub's platform, not LEVI's. It is the pragmatic
free tier — useful, but the pure self-reliant path is `levi serve` on
hardware you own.

## Honest gaps

- **TLS**: `levi serve` is plain HTTP. Localhost-only is the security
  model (like Forge). Public serving needs a reverse proxy with TLS
  (or Pages, which terminates TLS for you) — not yet built LEVI-native.
- **No multi-user auth**: the web app ships with auth disabled
  (`VITE_AUTH_ENABLED=false`); the database is PGlite in the browser,
  per-visitor. Shared state across visitors is not a thing yet.
- **Build still needs node/npm**: the frontend lives in the JS world —
  building it requires `npm ci`. Only the *serving* is stdlib-native.
  That's the JS ecosystem's toll, stated plainly.
- **No CI gate on the Pages workflow yet**: it builds on push; a failing
  web build fails the workflow visibly but nothing blocks the push.
- **Forge is localhost-only too**: `levi forge serve` binds 127.0.0.1 by
  design. A public Forge (code home for others) is a later increment.
