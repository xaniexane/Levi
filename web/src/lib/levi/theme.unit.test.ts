import { beforeEach, describe, expect, it } from "vitest";
import {
  applyTheme,
  DEFAULT_THEME,
  isTheme,
  readStoredTheme,
  THEME_STORAGE_KEY,
} from "./theme";

function memStorage(initial: Record<string, string> = {}): Storage {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    clear: () => map.clear(),
    key: (i: number) => [...map.keys()][i] ?? null,
    get length() {
      return map.size;
    },
  } as Storage;
}

describe("theme", () => {
  it("defaults to void when nothing is stored", () => {
    expect(readStoredTheme(memStorage())).toBe("void");
    expect(DEFAULT_THEME).toBe("void");
  });

  it("reads a persisted light theme", () => {
    const s = memStorage({
      [THEME_STORAGE_KEY]: JSON.stringify({ state: { theme: "light" }, version: 0 }),
    });
    expect(readStoredTheme(s)).toBe("light");
  });

  it("falls back to void on corrupt or unknown values", () => {
    expect(readStoredTheme(memStorage({ [THEME_STORAGE_KEY]: "not-json" }))).toBe("void");
    expect(
      readStoredTheme(
        memStorage({ [THEME_STORAGE_KEY]: JSON.stringify({ state: { theme: "neon" } }) }),
      ),
    ).toBe("void");
  });

  it("isTheme guards the union", () => {
    expect(isTheme("void")).toBe(true);
    expect(isTheme("light")).toBe(true);
    expect(isTheme("dark")).toBe(false);
    expect(isTheme(undefined)).toBe(false);
  });

  it("applyTheme writes data-theme on the document element", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    applyTheme("void");
    expect(document.documentElement.dataset.theme).toBe("void");
  });

  beforeEach(() => {
    delete document.documentElement.dataset.theme;
  });
});
