#!/usr/bin/env node
/**
 * Post-build shim for LEVI self-hosted static deployments.
 *
 * The TanStack Start + Nitro build emits an SSR server function plus static
 * assets, but no index.html — the HTML shell is rendered per request. Pure
 * static hosts (`levi serve`, GitHub Pages) need a shell that boots the
 * client SPA, so this script generates `.vercel/output/static/index.html`
 * from the build's own TanStack manifest (entry script) and CSS asset.
 * Asset paths are read out of the manifest, so whatever `--base` the build
 * used is honored as built.
 *
 * Usage (from web/, after a LEVI_SELFHOST=1 build):
 *   node scripts/static-shim.mjs
 */
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const staticDir = join(root, ".vercel/output/static");
const funcDir = join(root, ".vercel/output/functions/__server.func");

function fail(msg) {
  console.error(`[static-shim] ${msg}`);
  process.exit(1);
}

// 1. client entry script, from the TanStack Start manifest (hashed name).
let manifestFile;
try {
  manifestFile = readdirSync(funcDir).find(
    (f) => f.startsWith("_tanstack-start-manifest") && f.endsWith(".mjs"),
  );
} catch {
  fail("server function output not found — run `vite build` first");
}
if (!manifestFile) fail("tanstack manifest not found in server function output");
const manifest = readFileSync(join(funcDir, manifestFile), "utf8");
const entry = manifest.match(/src:\s*"([^"]+)"/)?.[1];
if (!entry) fail("no entry script found in tanstack manifest");

// 2. stylesheet, same assets directory as the entry.
const assetDir = entry.slice(0, entry.lastIndexOf("/") + 1);
let cssHref = null;
try {
  const cssFile = readdirSync(join(staticDir, "assets")).find((f) =>
    /^styles-.*\.css$/.test(f),
  );
  if (cssFile) cssHref = assetDir + cssFile;
} catch {
  /* no assets dir — css stays null */
}

// 3. base prefix, derived from the entry path ("/" or "/Levi/", …).
const base = entry.includes("/assets/") ? entry.slice(0, entry.indexOf("/assets/") + 1) : "/";

// 4. shell mirrors src/routes/__root.tsx head (title/meta/theme/favicon),
//    including the pre-paint theme snippet verbatim.
const themeSnippet = `(function(){try{var s=localStorage.getItem('levi-life');var t=s&&JSON.parse(s).state&&JSON.parse(s).state.theme;document.documentElement.dataset.theme=(t==='light')?'light':'void';}catch(e){document.documentElement.dataset.theme='void';}})();`;

const html = `<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LEVI</title>
<meta name="description" content="LEVI \u2014 companion intelligence. Friend, mentor, challenger, protector." />
<meta name="theme-color" content="#0a0a0c" />
<link rel="icon" type="image/svg+xml" href="${base}favicon.svg" />
${cssHref ? `<link rel="stylesheet" href="${cssHref}" />\n` : ""}<script>${themeSnippet}</script>
</head>
<body class="bg-bg text-fg">
<script type="module" async src="${entry}"></script>
</body>
</html>
`;

writeFileSync(join(staticDir, "index.html"), html);
console.log(`[static-shim] wrote index.html (entry ${entry})`);
