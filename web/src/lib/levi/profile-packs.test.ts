import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  applyPack,
  BUILTIN_PACKS,
  exportPack,
  FONT_ALLOWLIST,
  importPack,
  LIGHT_PACK,
  PACK_STORAGE_KEY,
  readPackStore,
  resolveActivePack,
  saveUserPack,
  setActivePackId,
  validatePack,
  VOID_PACK,
  type ProfilePack,
} from "./profile-packs.ts";
import { THEME_STORAGE_KEY } from "./theme.ts";

function makePack(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "test-pack",
    name: "Test Pack",
    colors: { bg: "#0a0a0c", accent: "#e2a63d", fg: "#f0eee8" },
    fonts: { heading: "Georgia", body: "System" },
    background: { kind: "color", value: "#0a0a0c" },
    density: "comfortable",
    glow: true,
    perPersona: {},
    ...overrides,
  };
}

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

function fakeDocument() {
  const vars = new Map<string, string>();
  const dataset: Record<string, string> = {};
  return {
    documentElement: {
      style: { setProperty: (n: string, v: string) => void vars.set(n, v) },
      dataset,
    } as unknown as Document["documentElement"],
    vars,
    dataset,
  };
}

describe("validatePack", () => {
  it("passes a valid pack", () => {
    const { ok, errors } = validatePack(makePack());
    assert.equal(ok, true);
    assert.deepEqual(errors, []);
  });

  it("rejects a bad hex color", () => {
    const { ok, errors } = validatePack(makePack({ colors: { bg: "#12x45z" } }));
    assert.equal(ok, false);
    assert.match(errors.join(" "), /pack\.colors/);
  });

  it("rejects a 4-digit hex (only 3/6/8 allowed)", () => {
    assert.equal(validatePack(makePack({ colors: { bg: "#1234" } })).ok, false);
    assert.equal(validatePack(makePack({ colors: { bg: "#123" } })).ok, true);
    assert.equal(validatePack(makePack({ colors: { bg: "#11223344" } })).ok, true);
  });

  it("rejects a non-allowlisted font", () => {
    const { ok, errors } = validatePack(
      makePack({ fonts: { heading: "Comic Sans MS", body: "System" } }),
    );
    assert.equal(ok, false);
    assert.match(errors.join(" "), /heading/);
  });

  it("rejects a javascript: image URL", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "javascript:alert(1)" } }),
    );
    assert.equal(ok, false);
  });

  it("rejects a data: image URL", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "data:image/png;base64,AAAA" } }),
    );
    assert.equal(ok, false);
  });

  it("rejects a blob: image URL", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "blob:https://x.example/abc" } }),
    );
    assert.equal(ok, false);
  });

  it("rejects a non-https image URL", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "http://x.example/a.png" } }),
    );
    assert.equal(ok, false);
  });

  it("accepts a valid https image URL", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "https://x.example/wallpaper.jpg" } }),
    );
    assert.equal(ok, true);
  });

  it("rejects an image URL that doesn't look like an image", () => {
    const { ok } = validatePack(
      makePack({ background: { kind: "image", value: "https://x.example/page.html" } }),
    );
    assert.equal(ok, false);
  });

  it("accepts a hex-only gradient", () => {
    const { ok } = validatePack(
      makePack({
        background: { kind: "gradient", value: "linear-gradient(to bottom, #0a0a0c, #e2a63d)" },
      }),
    );
    assert.equal(ok, true);
  });

  it("rejects a gradient with a non-hex color function", () => {
    const { ok } = validatePack(
      makePack({
        background: {
          kind: "gradient",
          value: "linear-gradient(to bottom, rgb(255,0,0), #e2a63d)",
        },
      }),
    );
    assert.equal(ok, false);
  });

  it("rejects a gradient with an unsafe token", () => {
    const { ok } = validatePack(
      makePack({
        background: { kind: "gradient", value: "linear-gradient(url(x), #e2a63d)" },
      }),
    );
    assert.equal(ok, false);
  });

  it("validates perPersona overrides too", () => {
    const bad = makePack({
      perPersona: { levi_wit: { colors: { accent: "not-a-hex" }, glow: "yes" } },
    });
    const { ok, errors } = validatePack(bad);
    assert.equal(ok, false);
    assert.match(errors.join(" "), /levi_wit/);
  });

  it("accepts valid perPersona overrides", () => {
    const good = makePack({
      perPersona: {
        levi_wit: {
          colors: { accent: "#ff0000" },
          background: { kind: "color", value: "#111111" },
          glow: false,
        },
      },
    });
    assert.equal(validatePack(good).ok, true);
  });

  it("rejects unknown top-level keys (closed schema)", () => {
    const { ok } = validatePack(makePack({ css: "body{display:none}" }));
    assert.equal(ok, false);
  });

  it("rejects unsafe color keys", () => {
    const { ok } = validatePack(makePack({ colors: { '--x":;}': "#000000" } }));
    assert.equal(ok, false);
  });
});

describe("importPack / exportPack", () => {
  it("round-trips a valid pack", () => {
    const pack = makePack() as unknown as ProfilePack;
    const imported = importPack(exportPack(pack));
    assert.equal(imported.ok, true);
    if (imported.ok) assert.deepEqual(imported.pack, pack);
  });

  it("re-validates on import and rejects tampered JSON", () => {
    const pack = makePack() as unknown as ProfilePack;
    const envelope = JSON.parse(exportPack(pack)) as { pack: Record<string, unknown> };
    (envelope.pack.colors as Record<string, string>).bg = "red";
    const imported = importPack(JSON.stringify(envelope));
    assert.equal(imported.ok, false);
    if (!imported.ok) assert.match(imported.errors.join(" "), /hex/);
  });

  it("rejects non-JSON", () => {
    const imported = importPack("not json at all");
    assert.equal(imported.ok, false);
  });

  it("accepts a bare pack object without the export envelope", () => {
    const imported = importPack(JSON.stringify(makePack()));
    assert.equal(imported.ok, true);
  });
});

describe("applyPack", () => {
  it("sets CSS variables and data attributes, never raw CSS", () => {
    const fake = fakeDocument();
    applyPack(VOID_PACK, { doc: fake as unknown as Document });
    assert.equal(fake.vars.get("--levi-color-accent"), "#e2a63d");
    assert.equal(fake.vars.get("--levi-accent"), "#e2a63d");
    assert.equal(fake.vars.get("--levi-bg-fill"), "#0a0a0c");
    assert.equal(fake.vars.get("--levi-bg-image"), "none");
    assert.match(fake.vars.get("--levi-font-heading") ?? "", /Georgia/);
    assert.match(fake.vars.get("--levi-font-body") ?? "", /system-ui/);
    assert.equal(fake.dataset.pack, "void");
    assert.equal(fake.dataset.density, "comfortable");
    assert.equal(fake.dataset.packGlow, "on");
  });

  it("applies perPersona overrides when the persona lens matches", () => {
    const fake = fakeDocument();
    const pack = makePack({
      perPersona: { levi_wit: { colors: { accent: "#ff0000" }, glow: false } },
    }) as unknown as ProfilePack;
    applyPack(pack, { personaId: "levi_wit", doc: fake as unknown as Document });
    assert.equal(fake.vars.get("--levi-accent"), "#ff0000");
    assert.equal(fake.vars.get("--levi-color-accent"), "#ff0000");
    assert.equal(fake.dataset.packGlow, "off");
  });

  it("ignores perPersona overrides for other personas", () => {
    const fake = fakeDocument();
    const pack = makePack({
      perPersona: { levi_wit: { colors: { accent: "#ff0000" } } },
    }) as unknown as ProfilePack;
    applyPack(pack, { personaId: "levi_companion", doc: fake as unknown as Document });
    assert.equal(fake.vars.get("--levi-accent"), "#e2a63d");
  });

  it("compiles image backgrounds to a quoted url()", () => {
    const fake = fakeDocument();
    const pack = makePack({
      background: { kind: "image", value: "https://x.example/wallpaper.jpg" },
    }) as unknown as ProfilePack;
    applyPack(pack, { doc: fake as unknown as Document });
    assert.equal(fake.vars.get("--levi-bg-image"), 'url("https://x.example/wallpaper.jpg")');
  });

  it("throws on an invalid pack", () => {
    const fake = fakeDocument();
    assert.throws(() =>
      applyPack(makePack({ colors: { bg: "red" } }) as unknown as ProfilePack, {
        doc: fake as unknown as Document,
      }),
    );
  });
});

describe("persistence", () => {
  it("uses a storage key that does not collide with the theme store", () => {
    assert.notEqual(PACK_STORAGE_KEY, THEME_STORAGE_KEY);
    assert.equal(PACK_STORAGE_KEY, "levi-packs");
  });

  it("saveUserPack validates, persists, and resolveActivePack falls back to void", () => {
    const storage = memStorage();
    const bad = saveUserPack(makePack({ id: "nope", colors: { bg: "red" } }), storage);
    assert.equal(bad.ok, false);

    const good = saveUserPack(makePack({ id: "mine", name: "Mine" }), storage);
    assert.equal(good.ok, true);

    setActivePackId("mine", storage);
    const store = readPackStore(storage);
    assert.equal(store.activeId, "mine");
    assert.equal(resolveActivePack(store).id, "mine");

    setActivePackId(null, storage);
    assert.equal(resolveActivePack(readPackStore(storage)).id, "void");
  });

  it("readPackStore drops invalid stored packs", () => {
    const storage = memStorage({
      [PACK_STORAGE_KEY]: JSON.stringify({
        activeId: "bad",
        packs: [makePack({ id: "bad", colors: { bg: "red" } }), makePack({ id: "ok" })],
      }),
    });
    const store = readPackStore(storage);
    assert.equal(store.packs.length, 1);
    assert.equal(store.activeId, null);
  });

  it("survives corrupt storage", () => {
    const store = readPackStore(memStorage({ [PACK_STORAGE_KEY]: "not-json" }));
    assert.deepEqual(store, { activeId: null, packs: [] });
  });
});

describe("builtin packs", () => {
  it("void and light are valid packs", () => {
    assert.equal(validatePack(VOID_PACK).ok, true);
    assert.equal(validatePack(LIGHT_PACK).ok, true);
    assert.equal(BUILTIN_PACKS.length, 2);
  });

  it("void reproduces the current dark theme tokens", () => {
    assert.equal(VOID_PACK.colors.bg, "#0a0a0c");
    assert.equal(VOID_PACK.colors.accent, "#e2a63d");
    assert.equal(VOID_PACK.colors.fg, "#f0eee8");
  });

  it("light reproduces the current light theme tokens", () => {
    assert.equal(LIGHT_PACK.colors.bg, "#faf8f4");
    assert.equal(LIGHT_PACK.colors.accent, "#b97f1f");
    assert.equal(LIGHT_PACK.colors.fg, "#1b1a17");
  });

  it("font allowlist is system stacks only", () => {
    assert.deepEqual([...FONT_ALLOWLIST].sort(), [
      "Courier New",
      "Georgia",
      "Impact",
      "System",
      "Trebuchet MS",
      "Verdana",
    ]);
  });
});
