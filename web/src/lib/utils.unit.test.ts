import { describe, expect, it } from "vitest";

import { cn, hashHex, hashInt, mulberry32, nowIso, seedFrom, uid } from "./utils";

describe("hashInt", () => {
  it("is deterministic for the same input", () => {
    expect(hashInt("levi")).toBe(hashInt("levi"));
  });

  it("distinguishes different inputs", () => {
    expect(hashInt("levi")).not.toBe(hashInt("omega"));
  });

  it("returns an unsigned 32-bit integer", () => {
    const h = hashInt("anything");
    expect(Number.isInteger(h)).toBe(true);
    expect(h).toBeGreaterThanOrEqual(0);
    expect(h).toBeLessThanOrEqual(0xffffffff);
  });
});

describe("hashHex", () => {
  it("returns 32 lowercase hex chars", () => {
    expect(hashHex("levi")).toMatch(/^[0-9a-f]{32}$/);
  });

  it("is deterministic", () => {
    expect(hashHex("seed")).toBe(hashHex("seed"));
  });
});

describe("mulberry32", () => {
  it("produces a repeatable sequence for the same seed", () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = [a(), a(), a(), a(), a()];
    const seqB = [b(), b(), b(), b(), b()];
    expect(seqA).toEqual(seqB);
  });

  it("produces values in [0, 1)", () => {
    const rand = mulberry32(7);
    for (let i = 0; i < 100; i++) {
      const v = rand();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe("seedFrom", () => {
  it("returns a hex string derived from the input", () => {
    expect(seedFrom("hello")).toMatch(/^[0-9a-f]+$/);
    expect(seedFrom("hello")).toBe(seedFrom("hello"));
    expect(seedFrom("hello")).not.toBe(seedFrom("goodbye"));
  });
});

describe("cn", () => {
  it("merges and dedupes tailwind classes", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    const showB = false;
    expect(cn("a", showB && "b", "c")).toBe("a c");
  });
});

describe("uid", () => {
  it("prefixes and uniquifies", () => {
    const a = uid("x");
    const b = uid("x");
    expect(a.startsWith("x_")).toBe(true);
    expect(a).not.toBe(b);
  });
});

describe("nowIso", () => {
  it("returns a parseable ISO timestamp", () => {
    expect(Number.isNaN(Date.parse(nowIso()))).toBe(false);
  });
});
