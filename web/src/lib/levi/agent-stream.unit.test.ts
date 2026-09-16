import { describe, expect, it } from "vitest";
import {
  AGENT_DEFAULT_URL,
  chunkReplyText,
  extractAgentReply,
  getAgentSessionId,
  mapAgentHttpStatus,
} from "./agent-stream";

describe("mapAgentHttpStatus", () => {
  it("maps auth failures to agent_unauthorized", () => {
    expect(mapAgentHttpStatus(401)).toBe("agent_unauthorized");
    expect(mapAgentHttpStatus(403)).toBe("agent_unauthorized");
  });

  it("maps 400 to agent_bad_request", () => {
    expect(mapAgentHttpStatus(400)).toBe("agent_bad_request");
  });

  it("maps everything else to agent_error", () => {
    expect(mapAgentHttpStatus(404)).toBe("agent_error");
    expect(mapAgentHttpStatus(500)).toBe("agent_error");
    expect(mapAgentHttpStatus(0)).toBe("agent_error");
  });
});

describe("extractAgentReply", () => {
  const okBody = (final: unknown) => ({
    session_id: "web-abc",
    transcript: { task: "hi", final, ok: true, error: null, steps: [] },
    context_pct: 4,
    compressed: false,
  });

  it("extracts the transcript final text", () => {
    expect(extractAgentReply(okBody("Hello there."))).toBe("Hello there.");
  });

  it("returns null when the turn failed", () => {
    expect(
      extractAgentReply({
        session_id: "web-abc",
        transcript: { final: "should not surface", ok: false, error: "boom" },
      }),
    ).toBeNull();
  });

  it("returns null for empty or missing final text", () => {
    expect(extractAgentReply(okBody(""))).toBeNull();
    expect(extractAgentReply(okBody("   "))).toBeNull();
    expect(extractAgentReply(okBody(null))).toBeNull();
    expect(extractAgentReply({ transcript: { ok: true } })).toBeNull();
  });

  it("returns null for malformed bodies", () => {
    expect(extractAgentReply(null)).toBeNull();
    expect(extractAgentReply("nope")).toBeNull();
    expect(extractAgentReply({})).toBeNull();
    expect(extractAgentReply({ transcript: null })).toBeNull();
  });
});

describe("chunkReplyText", () => {
  it("returns a single chunk for short text", () => {
    expect(chunkReplyText("Hi.")).toEqual(["Hi."]);
  });

  it("splits on sentence boundaries", () => {
    const chunks = chunkReplyText("First sentence. Second sentence! Third?");
    expect(chunks).toEqual(["First sentence.", "Second sentence!", "Third?"]);
  });

  it("round-trips: chunks join back to the original text", () => {
    const text =
      "This is a fairly long opening sentence that will definitely exceed the chunk budget on its own. Short one. " +
      "And a final sentence to close things out properly.";
    const chunks = chunkReplyText(text, 40);
    expect(chunks.every((c) => c.length <= 40 || !c.includes(" "))).toBe(true);
    // Word-group joins use single spaces; sentences keep their own spacing.
    expect(chunks.join(" ").replace(/\s+/g, " ")).toBe(text.replace(/\s+/g, " "));
  });

  it("handles text without sentence punctuation", () => {
    const chunks = chunkReplyText("one two three four five six", 10);
    expect(chunks.join(" ")).toBe("one two three four five six");
  });

  it("returns no empty chunks", () => {
    expect(chunkReplyText("")).toEqual([]);
    expect(chunkReplyText("A. B. C.", 64).every((c) => c.length > 0)).toBe(true);
  });
});

describe("getAgentSessionId", () => {
  function fakeStorage(initial: Record<string, string> = {}) {
    const map = new Map(Object.entries(initial));
    return {
      getItem: (k: string) => map.get(k) ?? null,
      setItem: (k: string, v: string) => {
        map.set(k, v);
      },
      peek: (k: string) => map.get(k),
    };
  }

  it("returns the stored id when one exists", () => {
    const s = fakeStorage({ "levi-agent-session": "web-existing" });
    expect(getAgentSessionId(s)).toBe("web-existing");
    expect(s.peek("levi-agent-session")).toBe("web-existing");
  });

  it("generates and persists an id when none exists", () => {
    const s = fakeStorage();
    const id = getAgentSessionId(s);
    expect(id).toMatch(/^web-[a-z0-9]{8}$/);
    expect(s.peek("levi-agent-session")).toBe(id);
    // Second call returns the persisted one.
    expect(getAgentSessionId(s)).toBe(id);
  });

  it("ignores blank stored values", () => {
    const s = fakeStorage({ "levi-agent-session": "  " });
    const id = getAgentSessionId(s);
    expect(id).toMatch(/^web-[a-z0-9]{8}$/);
  });

  it("survives storage that throws", () => {
    const throwing = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    expect(getAgentSessionId(throwing)).toMatch(/^web-[a-z0-9]{8}$/);
  });
});

describe("AGENT_DEFAULT_URL", () => {
  it("points at the agent server's documented default", () => {
    expect(AGENT_DEFAULT_URL).toBe("http://127.0.0.1:8765");
  });
});
