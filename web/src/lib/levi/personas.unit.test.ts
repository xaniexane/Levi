import { describe, expect, it } from "vitest";
import { FEATURED_PERSONAS, getPersona, isRegister, PERSONAS, REGISTERS } from "./personas";

describe("personas / LEVI registers", () => {
  it("exposes exactly 14 LEVI-original registers", () => {
    expect(REGISTERS).toHaveLength(14);
    expect(REGISTERS.every((r) => r.register)).toBe(true);
  });

  it("includes the Warm and Bold variants", () => {
    const ids = REGISTERS.map((r) => r.id);
    expect(ids).toContain("levi_companion");
    expect(ids).toContain("levi_wit");
  });

  it("features Warm and Bold first in the switcher", () => {
    expect(FEATURED_PERSONAS[0]).toBe("levi_companion");
    expect(FEATURED_PERSONAS[1]).toBe("levi_wit");
  });

  it("merges registers into PERSONAS with unique ids", () => {
    const ids = PERSONAS.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const r of REGISTERS) {
      expect(ids).toContain(r.id);
    }
  });

  it("isRegister distinguishes registers from legacy personas", () => {
    expect(isRegister("levi_companion")).toBe(true);
    expect(isRegister("levi")).toBe(true);
    expect(isRegister("normal")).toBe(false);
    expect(isRegister("void")).toBe(false);
  });

  it("getPersona resolves registers and falls back safely", () => {
    expect(getPersona("levi_wit").name).toBe("Bold");
    expect(getPersona("levi_companion").name).toBe("Warm");
    expect(getPersona("levi").name).toBe("Calm");
    expect(getPersona("levi_companion").style).toMatch(/genuinely helpful/i);
    // Unknown ids fall back to the default persona rather than crashing.
    expect(getPersona("nope" as never).id).toBe("normal");
  });
});
