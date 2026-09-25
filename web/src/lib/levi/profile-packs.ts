/**
 * MySpace-era profile packs for the LEVI web UI.
 *
 * A pack is user-authored theming data — colors, fonts, background, density,
 * glow, and per-persona overrides — that compiles down to CSS custom
 * properties and data attributes on <html>. Packs NEVER carry raw CSS: the
 * validator parses every value into a closed grammar (hex colors, an
 * allowlisted set of system font stacks, https image URLs, and a strict
 * linear/radial-gradient subset), and `applyPack` is the only DOM writer —
 * it emits setProperty() calls, never innerHTML / style injection.
 *
 * Persistence lives under PACK_STORAGE_KEY ("levi-packs"), separate from the
 * theme store ("levi-life" in theme.ts), so packs never collide with the
 * void/light toggle.
 */

/* ------------------------------------------------------------------ types */

export type PackDensity = "cozy" | "comfortable" | "compact";
export type PackBackgroundKind = "color" | "gradient" | "image";

export interface PackBackground {
  kind: PackBackgroundKind;
  value: string;
}

/** Per-persona-lens overrides. Everything is optional; base pack wins when unset. */
export interface PackOverrides {
  colors?: Record<string, string>;
  background?: PackBackground;
  glow?: boolean;
}

export interface ProfilePack {
  id: string;
  name: string;
  colors: Record<string, string>;
  fonts: { heading: string; body: string };
  background: PackBackground;
  density: PackDensity;
  glow: boolean;
  perPersona: Record<string, Partial<PackOverrides>>;
}

export type PackValidation = { ok: boolean; errors: string[] };
export type PackImportResult = { ok: true; pack: ProfilePack } | { ok: false; errors: string[] };

/** localStorage key. Deliberately distinct from THEME_STORAGE_KEY ("levi-life"). */
export const PACK_STORAGE_KEY = "levi-packs";

export const PACK_DENSITIES: readonly PackDensity[] = ["cozy", "comfortable", "compact"];

/* ------------------------------------------------------- font allowlist */

/**
 * Fixed allowlist of local system font stacks. Local-first: no remote font
 * fetching, ever. applyPack maps these names to the stacks below — the raw
 * string from a pack never reaches CSS, so it can't smuggle in a
 * `font-family` injection.
 */
export const FONT_ALLOWLIST: readonly string[] = [
  "System",
  "Georgia",
  "Courier New",
  "Verdana",
  "Trebuchet MS",
  "Impact",
];

const FONT_STACKS: Record<string, string> = {
  System: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`,
  Georgia: `Georgia, "Times New Roman", serif`,
  "Courier New": `"Courier New", Courier, monospace`,
  Verdana: `Verdana, Geneva, sans-serif`,
  "Trebuchet MS": `"Trebuchet MS", "Segoe UI", sans-serif`,
  Impact: `Impact, Haettenschweiler, sans-serif`,
};

/* ------------------------------------------------------------ validation */

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
const COLOR_KEY_RE = /^[a-zA-Z][a-zA-Z0-9_-]{0,31}$/;
const PACK_ID_RE = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/;
const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|avif|bmp|svg|ico)([?#]|$)/i;
/** Anything that could smuggle code out of a quoted CSS url("..."). */
const UNSAFE_URL_CHARS_RE = /[\s"'`\\<>]/;

/** Safe direction keywords for the gradient subset (parse, don't pass through raw). */
const GRADIENT_KEYWORDS = new Set([
  "to",
  "at",
  "center",
  "top",
  "bottom",
  "left",
  "right",
  "circle",
  "ellipse",
  "closest-side",
  "closest-corner",
  "farthest-side",
  "farthest-corner",
]);

const PACK_TOP_LEVEL_KEYS = new Set([
  "id",
  "name",
  "colors",
  "fonts",
  "background",
  "density",
  "glow",
  "perPersona",
]);

const OVERRIDE_KEYS = new Set(["colors", "background", "glow"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isHex(value: unknown): value is string {
  return typeof value === "string" && HEX_RE.test(value);
}

function err(errors: string[], path: string, message: string): void {
  errors.push(`${path}: ${message}`);
}

/**
 * Parse a gradient() value into a canonical string. Returns null when the
 * value is anything outside the strict subset: linear-gradient() /
 * radial-gradient() whose comma-separated arguments are hex colors or safe
 * direction keywords. Parens, functions, angles, percentages, and every other
 * CSS primitive are rejected.
 */
export function parseGradient(value: string): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  const match = /^(linear-gradient|radial-gradient)\((.*)\)$/i.exec(trimmed);
  if (!match) return null;
  const name = match[1].toLowerCase();
  const rawArgs = match[2];

  // Split on top-level commas only; nested parens are forbidden outright.
  const args: string[] = [];
  let depth = 0;
  let current = "";
  for (const ch of rawArgs) {
    if (ch === "(" || ch === ")") {
      depth += ch === "(" ? 1 : -1;
      if (depth < 0) return null;
      current += ch;
    } else if (ch === "," && depth === 0) {
      args.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  args.push(current.trim());
  if (depth !== 0 || args.length === 0 || args.some((a) => a === "")) return null;

  const canonicalArgs: string[] = [];
  for (const arg of args) {
    const tokens = arg.split(/\s+/);
    for (const token of tokens) {
      if (HEX_RE.test(token)) continue;
      if (GRADIENT_KEYWORDS.has(token.toLowerCase())) continue;
      return null;
    }
    // First token of a direction group may be "to"/"at"; a bare color list is fine too.
    canonicalArgs.push(tokens.join(" "));
  }
  return `${name}(${canonicalArgs.join(", ")})`;
}

function validateBackground(bg: unknown, path: string, errors: string[]): void {
  if (!isRecord(bg)) {
    err(errors, path, "must be an object");
    return;
  }
  for (const key of Object.keys(bg)) {
    if (key !== "kind" && key !== "value") err(errors, path, `unknown key "${key}"`);
  }
  const { kind, value } = bg;
  if (kind !== "color" && kind !== "gradient" && kind !== "image") {
    err(errors, path, `kind must be "color", "gradient" or "image"`);
    return;
  }
  if (typeof value !== "string" || value.length === 0 || value.length > 2048) {
    err(errors, path, "value must be a non-empty string (max 2048 chars)");
    return;
  }
  if (kind === "color") {
    if (!isHex(value)) err(errors, path, "color background must be a hex color like #0a0a0c");
  } else if (kind === "gradient") {
    if (parseGradient(value) === null) {
      err(
        errors,
        path,
        "gradient must be linear-gradient()/radial-gradient() with hex colors and safe direction keywords only",
      );
    }
  } else {
    validateImageUrl(value, path, errors);
  }
}

function validateImageUrl(value: string, path: string, errors: string[]): void {
  if (UNSAFE_URL_CHARS_RE.test(value)) {
    err(errors, path, "image URL contains unsafe characters");
    return;
  }
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    err(errors, path, "image URL is not a valid URL");
    return;
  }
  if (url.protocol !== "https:") {
    err(errors, path, `image URL must use https:// (got "${url.protocol}")`);
    return;
  }
  if (!IMAGE_EXT_RE.test(url.pathname)) {
    err(errors, path, "image URL must look like an image (png/jpg/gif/webp/avif/bmp/svg/ico)");
  }
}

function validateColors(colors: unknown, path: string, errors: string[]): void {
  if (!isRecord(colors)) {
    err(errors, path, "must be an object");
    return;
  }
  const keys = Object.keys(colors);
  if (keys.length === 0) err(errors, path, "must define at least one color");
  for (const key of keys) {
    if (!COLOR_KEY_RE.test(key)) {
      err(errors, path, `color key "${key}" must be a safe identifier`);
      continue;
    }
    if (!isHex(colors[key])) {
      err(
        errors,
        path,
        `color "${key}" must be a hex color like #e2a63d, got ${JSON.stringify(colors[key])}`,
      );
    }
  }
}

function validateOverrides(
  overrides: unknown,
  path: string,
  errors: string[],
): overrides is Partial<PackOverrides> {
  if (!isRecord(overrides)) {
    err(errors, path, "must be an object");
    return false;
  }
  for (const key of Object.keys(overrides)) {
    if (!OVERRIDE_KEYS.has(key)) err(errors, path, `unknown override key "${key}"`);
  }
  if (overrides.colors !== undefined) validateColors(overrides.colors, `${path}.colors`, errors);
  if (overrides.background !== undefined)
    validateBackground(overrides.background, `${path}.background`, errors);
  if (overrides.glow !== undefined && typeof overrides.glow !== "boolean") {
    err(errors, path, "glow must be a boolean");
  }
  return true;
}

/**
 * STRICT validation of a profile pack. Closed schema (unknown keys rejected),
 * hex-only colors, allowlisted fonts, parsed gradients, https image URLs.
 * Returns { ok, errors } — errors is empty when ok.
 */
export function validatePack(pack: unknown): PackValidation {
  const errors: string[] = [];
  if (!isRecord(pack)) {
    return { ok: false, errors: ["pack: must be an object"] };
  }
  for (const key of Object.keys(pack)) {
    if (!PACK_TOP_LEVEL_KEYS.has(key)) err(errors, "pack", `unknown key "${key}"`);
  }

  if (typeof pack.id !== "string" || !PACK_ID_RE.test(pack.id)) {
    err(errors, "pack.id", "must be a 1-64 char identifier (letters, digits, - and _)");
  }
  if (typeof pack.name !== "string" || pack.name.trim().length === 0 || pack.name.length > 120) {
    err(errors, "pack.name", "must be a non-empty string (max 120 chars)");
  }
  validateColors(pack.colors, "pack.colors", errors);

  if (!isRecord(pack.fonts)) {
    err(errors, "pack.fonts", "must be an object with heading and body");
  } else {
    for (const key of Object.keys(pack.fonts)) {
      if (key !== "heading" && key !== "body") err(errors, "pack.fonts", `unknown key "${key}"`);
    }
    for (const slot of ["heading", "body"] as const) {
      const font = (pack.fonts as Record<string, unknown>)[slot];
      if (typeof font !== "string" || !FONT_ALLOWLIST.includes(font)) {
        err(errors, `pack.fonts.${slot}`, `must be one of: ${FONT_ALLOWLIST.join(", ")}`);
      }
    }
  }

  validateBackground(pack.background, "pack.background", errors);

  if (typeof pack.density !== "string" || !PACK_DENSITIES.includes(pack.density as PackDensity)) {
    err(errors, "pack.density", `must be one of: ${PACK_DENSITIES.join(", ")}`);
  }
  if (typeof pack.glow !== "boolean") {
    err(errors, "pack.glow", "must be a boolean");
  }

  if (!isRecord(pack.perPersona)) {
    err(errors, "pack.perPersona", "must be an object mapping persona lens ids to overrides");
  } else {
    for (const [personaId, overrides] of Object.entries(pack.perPersona)) {
      if (personaId.length === 0 || personaId.length > 64) {
        err(errors, `pack.perPersona`, `persona lens id "${personaId}" must be 1-64 chars`);
        continue;
      }
      validateOverrides(overrides, `pack.perPersona["${personaId}"]`, errors);
    }
  }

  return { ok: errors.length === 0, errors };
}

/* ------------------------------------------------------------ applyPack */

/** Well-known color keys get short canonical variable names; every key also
 *  gets --levi-color-<key>. */
const CANONICAL_COLOR_VARS: Record<string, string> = {
  bg: "--levi-bg",
  surface: "--levi-surface",
  elevated: "--levi-elevated",
  fg: "--levi-fg",
  muted: "--levi-muted",
  subtle: "--levi-subtle",
  accent: "--levi-accent",
  accentfg: "--levi-accent-fg",
  accent_fg: "--levi-accent-fg",
  border: "--levi-border",
  danger: "--levi-danger",
  ok: "--levi-ok",
  live: "--levi-live",
};

function cssVarForColorKey(key: string): string {
  return `--levi-color-${key.toLowerCase()}`;
}

function setColors(el: HTMLElement, colors: Record<string, string>): void {
  for (const [key, value] of Object.entries(colors)) {
    el.style.setProperty(cssVarForColorKey(key), value);
    const canonical = CANONICAL_COLOR_VARS[key.toLowerCase()];
    if (canonical) el.style.setProperty(canonical, value);
  }
}

function backgroundToVars(bg: PackBackground): { fill: string; image: string } {
  if (bg.kind === "color") return { fill: bg.value, image: "none" };
  if (bg.kind === "gradient") {
    const parsed = parseGradient(bg.value);
    return { fill: "transparent", image: parsed ?? "none" };
  }
  return { fill: "var(--levi-bg, #000)", image: `url("${bg.value}")` };
}

/**
 * Compile a validated pack to CSS custom properties + data attributes on
 * <html>. Pure function of the validated pack (+ optional persona lens id,
 * whose overrides win). Throws when the pack fails validation.
 *
 * Emits only setProperty() calls and dataset writes — never raw CSS.
 */
export function applyPack(
  pack: ProfilePack,
  options: { personaId?: string; doc?: Document } = {},
): void {
  const { ok, errors } = validatePack(pack);
  if (!ok) throw new Error(`invalid profile pack: ${errors.join("; ")}`);
  const doc = options.doc ?? globalThis.document;
  const el = doc.documentElement;

  setColors(el, pack.colors);

  const overrides =
    options.personaId !== undefined ? pack.perPersona[options.personaId] : undefined;
  if (overrides?.colors) setColors(el, overrides.colors);

  const bg = overrides?.background ?? pack.background;
  const { fill, image } = backgroundToVars(bg);
  el.style.setProperty("--levi-bg-fill", fill);
  el.style.setProperty("--levi-bg-image", image);

  el.style.setProperty(
    "--levi-font-heading",
    FONT_STACKS[pack.fonts.heading] ?? FONT_STACKS.System,
  );
  el.style.setProperty("--levi-font-body", FONT_STACKS[pack.fonts.body] ?? FONT_STACKS.System);

  const glow = overrides?.glow ?? pack.glow;
  el.dataset.pack = pack.id;
  el.dataset.density = pack.density;
  el.dataset.packGlow = glow ? "on" : "off";
}

/* -------------------------------------------------------- persistence */

export interface PackStoreShape {
  activeId: string | null;
  packs: ProfilePack[];
}

/** Read the pack store, re-validating every stored pack. Invalid packs are
 *  dropped; an unknown activeId falls back to null. */
export function readPackStore(
  storage: Pick<Storage, "getItem"> = globalThis.localStorage,
): PackStoreShape {
  try {
    const raw = storage.getItem(PACK_STORAGE_KEY);
    if (!raw) return { activeId: null, packs: [] };
    const parsed = JSON.parse(raw) as { activeId?: unknown; packs?: unknown };
    const packs: ProfilePack[] = [];
    if (Array.isArray(parsed.packs)) {
      for (const candidate of parsed.packs) {
        if (validatePack(candidate).ok) packs.push(candidate as ProfilePack);
      }
    }
    const activeId =
      typeof parsed.activeId === "string" && packs.some((p) => p.id === parsed.activeId)
        ? parsed.activeId
        : null;
    return { activeId, packs };
  } catch {
    return { activeId: null, packs: [] };
  }
}

export function writePackStore(
  store: PackStoreShape,
  storage: Pick<Storage, "setItem"> = globalThis.localStorage,
): void {
  storage.setItem(PACK_STORAGE_KEY, JSON.stringify(store));
}

/** Validate and upsert a user pack into the store. Returns errors on failure. */
export function saveUserPack(
  pack: unknown,
  storage: Pick<Storage, "getItem" | "setItem"> = globalThis.localStorage,
): PackImportResult {
  const { ok, errors } = validatePack(pack);
  if (!ok) return { ok: false, errors };
  const store = readPackStore(storage);
  const valid = pack as ProfilePack;
  const idx = store.packs.findIndex((p) => p.id === valid.id);
  if (idx >= 0) store.packs[idx] = valid;
  else store.packs.push(valid);
  writePackStore(store, storage);
  return { ok: true, pack: valid };
}

export function setActivePackId(
  id: string | null,
  storage: Pick<Storage, "getItem" | "setItem"> = globalThis.localStorage,
): void {
  const store = readPackStore(storage);
  store.activeId = id;
  writePackStore(store, storage);
}

/** The active user pack, or the void builtin when none is selected. */
export function resolveActivePack(store: PackStoreShape): ProfilePack {
  if (store.activeId) {
    const found = store.packs.find((p) => p.id === store.activeId);
    if (found) return found;
  }
  return VOID_PACK;
}

/* ------------------------------------------------------ export / import */

const EXPORT_FORMAT = "levi-profile-pack";
const EXPORT_VERSION = 1;

/** Serialize a pack for sharing. Throws when the pack fails validation. */
export function exportPack(pack: ProfilePack): string {
  const { ok, errors } = validatePack(pack);
  if (!ok) throw new Error(`cannot export invalid profile pack: ${errors.join("; ")}`);
  return JSON.stringify({ format: EXPORT_FORMAT, version: EXPORT_VERSION, pack });
}

/**
 * Import a pack from JSON. The payload is re-validated from scratch — never
 * trusted — and returns { ok: false, errors } instead of throwing on bad data.
 */
export function importPack(json: string): PackImportResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch {
    return { ok: false, errors: ["import: not valid JSON"] };
  }
  let candidate: unknown = parsed;
  if (isRecord(parsed) && parsed.format === EXPORT_FORMAT) {
    if (parsed.version !== EXPORT_VERSION) {
      return {
        ok: false,
        errors: [`import: unsupported pack version ${JSON.stringify(parsed.version)}`],
      };
    }
    candidate = parsed.pack;
  }
  const { ok, errors } = validatePack(candidate);
  if (!ok) return { ok: false, errors: errors.map((e) => `import: ${e}`) };
  return { ok: true, pack: candidate as ProfilePack };
}

/* -------------------------------------------------------------- builtins */

/**
 * Builtin packs reproduce the current void/light themes (see styles.css)
 * so existing behavior is preserved when packs land on top of the toggle.
 */
export const VOID_PACK: ProfilePack = {
  id: "void",
  name: "Void",
  colors: {
    bg: "#0a0a0c",
    surface: "#121215",
    elevated: "#1b1b20",
    fg: "#f0eee8",
    muted: "#9b998f",
    subtle: "#6f6d67",
    accent: "#e2a63d",
    accentFg: "#141005",
    danger: "#c45c4a",
    ok: "#6fbf73",
    live: "#e2a63d",
  },
  fonts: { heading: "Georgia", body: "System" },
  background: { kind: "color", value: "#0a0a0c" },
  density: "comfortable",
  glow: true,
  perPersona: {},
};

export const LIGHT_PACK: ProfilePack = {
  id: "light",
  name: "Light",
  colors: {
    bg: "#faf8f4",
    surface: "#ffffff",
    elevated: "#f1ede6",
    fg: "#1b1a17",
    muted: "#6d6a61",
    subtle: "#a5a198",
    accent: "#b97f1f",
    accentFg: "#fffaf0",
    danger: "#b04a38",
    ok: "#3f8f44",
    live: "#b97f1f",
  },
  fonts: { heading: "Georgia", body: "System" },
  background: { kind: "color", value: "#faf8f4" },
  density: "comfortable",
  glow: false,
  perPersona: {},
};

export const BUILTIN_PACKS: readonly ProfilePack[] = [VOID_PACK, LIGHT_PACK];

export function builtinPack(id: string): ProfilePack | undefined {
  return BUILTIN_PACKS.find((p) => p.id === id);
}
