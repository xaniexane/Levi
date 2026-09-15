import { describe, expect, it } from "vitest";
import { FEATURED_PERSONAS, getPersona, isRegister, PERSONAS, REGISTERS } from "./personas";

describe("personas / KAI-9000 registers", () => {
  it("exposes exactly 14 LEVI-original registers", () => {
    expect(REGISTERS).toHaveLength(14);
    expect(REGISTERS.every((r) => r.register)).toBe(true);
  });

  it("includes the Warm and Bold variants", () => {
    const ids = REGISTERS.map((r) => r.id);
    expect(ids).toContain("kai_9000_muse");
    expect(ids).toContain("kai_9000_grok");
  });

  it("features Warm and Bold first in the switcher", () => {
    expect(FEATURED_PERSONAS[0]).toBe("kai_9000_muse");
    expect(FEATURED_PERSONAS[1]).toBe("kai_9000_grok");
  });

  it("merges registers into PERSONAS with unique ids", () => {
    const ids = PERSONAS.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const r of REGISTERS) {
      expect(ids).toContain(r.id);
    }
  });

  it("isRegister distinguishes registers from legacy personas", () => {
    expect(isRegister("kai_9000_muse")).toBe(true);
    expect(isRegister("kai_9000")).toBe(true);
    expect(isRegister("normal")).toBe(false);
    expect(isRegister("void")).toBe(false);
  });

  it("getPersona resolves registers and falls back safely", () => {
    expect(getPersona("kai_9000_grok").name).toBe("Bold");
    expect(getPersona("kai_9000_muse").name).toBe("Warm");
    expect(getPersona("kai_9000").name).toBe("Calm");
    expect(getPersona("kai_9000_muse").style).toMatch(/genuinely helpful/i);
    // Unknown ids fall back to the default persona rather than crashing.
    expect(getPersona("nope" as never).id).toBe("normal");
  });
});
