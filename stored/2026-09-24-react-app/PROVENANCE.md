# Why this app was moved out of web/ — provenance

**Moved:** 2026-09-24 (~23:40 CDT)
**By whose ruling:** Chauncey — "Replace with real" (in reply to the void-mind v1 mockup review).
**Law applied:** nothing-thrown-away — removed and STORED, never deleted.

## What this was

The LEVI web app as a TanStack Start + React 19 + Tailwind v4 + PGLite/Better-Auth
scaffold, built under the app-builder sandbox contract (`AGENTS.md`, kept in
this bundle). Dev entry was `npm run dev` on `0.0.0.0:8080`; production builds
went through Nitro with a Vercel preset.

## Why it was replaced

Chauncey approved the void-mind v1 mockup (`web/mockups/void-mind-v1.html`,
commit `9d0a776c`) and ordered the real build to REPLACE this app, not live
beside it. The replacement:

- `web/index.html` — the real void UI (single file, zero build step, zero
  external requests; the mockup's visual spec made real).
- `core/levi/serve/void_api.py` — the stdlib daemon API it talks to
  (`/api/health`, `/api/registers`, `/api/growth`, `/api/journal`,
  `/api/model`, `/api/chat`, `/api/note`, `/api/fork`, `/api/session/*`),
  mounted by `core/levi/serve/server.py` (`levi serve`).
- Local-first: the React app's platform PWA plugin injected a remote
  `grok.com` script tag; the replacement phones home to nothing.

## What's in this bundle

Everything that was `web/` except the replacement and the mockups:
`src/`, `server/`, `scripts/`, `public/`, `package.json`,
`package-lock.json`, `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`,
`eslint.config.mjs`, `startup.sh`, `AGENTS.md`, `docs/`.

**Not included:** `web/node_modules/` (427MB) — removed, not stored. It is
byte-reproducible from the `package-lock.json` in this bundle via
`npm ci`. No original work lived in it.

## How to restore

From the repo root:

```sh
mkdir -p web/restored-react-app
cp -r stored/2026-09-24-react-app/* web/restored-react-app/
cd web/restored-react-app && npm ci && npm run dev
```

Restoring does not touch the void UI (`web/index.html`), which lives beside
whatever is restored.
