import { describe, expect, it } from "vitest";
import { parseStreamLine } from "./stream-protocol";

describe("parseStreamLine", () => {
  it("parses token events", () => {
    expect(parseStreamLine('data: {"t":"hello"}')).toEqual({
      kind: "token",
      token: "hello",
    });
  });

  it("parses done and error events", () => {
    expect(parseStreamLine('data: {"done":true}')).toEqual({ kind: "done" });
    expect(parseStreamLine('data: {"error":"rate_limited"}')).toEqual({
      kind: "error",
      error: "rate_limited",
    });
  });

  it("ignores non-data lines, blanks, and malformed JSON", () => {
    expect(parseStreamLine(": keep-alive")).toBeNull();
    expect(parseStreamLine("")).toBeNull();
    expect(parseStreamLine("data:")).toBeNull();
    expect(parseStreamLine("data: {oops")).toBeNull();
    expect(parseStreamLine('data: {"unrelated":1}')).toBeNull();
  });

  it("tolerates surrounding whitespace", () => {
    expect(parseStreamLine('  data: {"t":"x"}  ')).toEqual({
      kind: "token",
      token: "x",
    });
  });
});
