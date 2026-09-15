/**
 * Theme plumbing — pure, unit-tested.
 *
 * The zustand store persists under THEME_STORAGE_KEY ("levi-life"); the
 * pre-paint inline script in __root.tsx reads the same key so the theme
 * applies before first paint (no flash). `applyTheme` is the single DOM
 * writer; the store's setTheme calls it, and useThemeSync covers reloads.
 */

export type Theme = "void" | "light";

export const THEME_STORAGE_KEY = "levi-life";

export const DEFAULT_THEME: Theme = "void";

export function isTheme(value: unknown): value is Theme {
  return value === "void" || value === "light";
}

/** Read the persisted theme without touching the store (pre-paint safe). */
export function readStoredTheme(
  storage: Pick<Storage, "getItem"> = globalThis.localStorage,
): Theme {
  try {
    const raw = storage.getItem(THEME_STORAGE_KEY);
    if (!raw) return DEFAULT_THEME;
    const parsed = JSON.parse(raw) as { state?: { theme?: unknown } };
    const t = parsed?.state?.theme;
    return isTheme(t) ? t : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

/** The one DOM write for theme switching. */
export function applyTheme(theme: Theme, doc: Document = globalThis.document): void {
  doc.documentElement.dataset.theme = theme;
}
