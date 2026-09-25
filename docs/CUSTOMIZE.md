# Customizing LEVI: Profile Packs

Profile packs are MySpace-era theming for the LEVI web UI — a JSON document
that restyles colors, fonts, background, density, and glow, optionally per
persona lens. Packs are authored as data, validated strictly, and compiled to
**CSS custom properties and data attributes only**.

Source: `web/src/lib/levi/profile-packs.ts` (validators, DOM writer,
persistence, builtins). Re-exported from `web/src/lib/levi/theme.ts` so the
pack API rides next to the void/light theme toggle.

## The law: CSS variables only, never raw CSS

Packs carry **no CSS**. No `style` strings, no selectors, no `@import`, no
`url()` written by hand. Every value is parsed into a closed grammar:

- **colors**: `#rgb`, `#rrggbb`, or `#rrggbbaa` hex only — regex
  `^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$`. Named colors (`red`),
  `rgb()`, `oklch()`, `color-mix()`, `var()` are all rejected.
- **fonts**: a fixed allowlist of local system stacks — `System`, `Georgia`,
  `Courier New`, `Verdana`, `Trebuchet MS`, `Impact`. Local-first: no remote
  font fetching. The raw string never reaches CSS; `applyPack` maps the name
  to a hardcoded stack, so a font name can't smuggle a `font-family`
  injection.
- **backgrounds**:
  - `color` → hex color.
  - `gradient` → only `linear-gradient()` / `radial-gradient()` whose
    arguments are hex colors or safe direction keywords (`to`, `at`,
    `center`, `top`, `bottom`, `left`, `right`, `circle`, `ellipse`,
    `closest-side`, …). Parsed token-by-token and re-emitted canonically;
    angles, percentages, functions, nested parens are rejected.
  - `image` → `https://` only, must end in a real image extension
    (png/jpg/gif/webp/avif/bmp/svg/ico), and `javascript:`, `data:`, `blob:`,
    `http:` and quote/whitespace-bearing URLs are rejected. Emitted as a
    quoted `url("...")` custom property.
- **schema**: closed — unknown keys at any level are rejected, and color keys
  must be safe identifiers.

`validatePack(pack)` returns `{ ok, errors }` and never throws. `applyPack`
is the single DOM writer: it calls `validatePack` first (throwing on
invalid input) and then only issues `setProperty()` calls and `dataset`
writes.

## Pack format

```jsonc
{
  "id": "midnight-arcade",          // 1-64 chars, [a-zA-Z0-9_-]
  "name": "Midnight Arcade",        // display name, max 120 chars
  "colors": {
    "bg": "#0a0a0c",               // every value: hex only
    "accent": "#e2a63d",
    "fg": "#f0eee8"
  },
  "fonts": { "heading": "Georgia", "body": "System" },  // allowlist only
  "background": { "kind": "color", "value": "#0a0a0c" },
  "density": "comfortable",         // "cozy" | "comfortable" | "compact"
  "glow": true,
  "perPersona": {                  // per persona lens id (optional)
    "levi_wit": {
      "colors": { "accent": "#ff3355" },
      "background": { "kind": "gradient",
        "value": "radial-gradient(circle, #1a1a20, #0a0a0c)" },
      "glow": false
    }
  }
}
```

Every color key becomes `--levi-color-<key>`; well-known keys (`bg`,
`surface`, `elevated`, `fg`, `muted`, `subtle`, `accent`, `accentFg`,
`border`, `danger`, `ok`, `live`) also get canonical names (`--levi-bg`,
`--levi-accent`, `--levi-fg`, …). Backgrounds emit `--levi-bg-fill` and
`--levi-bg-image`; fonts emit `--levi-font-heading` / `--levi-font-body`.
`dataset.pack`, `dataset.density`, and `dataset.packGlow` carry the rest.

## Export / import

```ts
import { exportPack, importPack } from "./theme.ts";

const json = exportPack(pack);          // JSON string, validated first (throws if invalid)
const result = importPack(json);        // { ok: true, pack } | { ok: false, errors }
if (!result.ok) console.error(result.errors);
```

Imported JSON is **re-validated from scratch** — a tampered or hand-written
payload with a bad hex, a `javascript:` URL, or an unknown key is rejected
with error messages. `importPack` also accepts a bare pack object without the
export envelope.

## Per-persona styling

`perPersona` maps a persona lens id (e.g. `levi_wit`, `levi_companion` —
see `personas.ts`) to `{ colors?, background?, glow? }` overrides. They are
validated with the same strictness as the base pack. `applyPack(pack,
{ personaId })` applies base first, then merges the matching lens's
overrides; unknown lens ids are simply ignored.

## Persistence

- Key: `levi-packs` (`PACK_STORAGE_KEY`) — never collides with the theme
  store `levi-life`.
- `saveUserPack(pack, storage?)` — validates, then upserts into the store;
  returns `{ ok, errors }`.
- `setActivePackId(id | null, storage?)` + `resolveActivePack(store)` —
  resolves the active user pack, falling back to the `void` builtin.
- `readPackStore(storage?)` re-validates every stored pack and drops invalid
  ones, so a corrupt or hand-edited store can't poison the UI.

## Builtin packs

`VOID_PACK` and `LIGHT_PACK` reproduce the current themes token-for-token
(see `src/styles.css`), so existing behavior is preserved; `packForTheme(theme)`
maps the void/light toggle onto its builtin pack. The toggle itself is
unchanged: `applyTheme` still writes `dataset.theme`, and packs sit on top as
an independent layer.
