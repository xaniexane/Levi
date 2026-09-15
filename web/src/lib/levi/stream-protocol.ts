/**
 * Minimal SSE protocol shared between the leviStream server function and the
 * browser client. Pure — no server or DOM imports, safe for the fast unit
 * suite. Server emits `data: {"t":"token"}` lines, one `data: {"error":"..."}`
 * on failure, and `data: {"done":true}` to close.
 */

export type StreamChunk =
  | { kind: "token"; token: string }
  | { kind: "done" }
  | { kind: "error"; error: string };

/** Parse one line of the protocol; anything else → null. */
export function parseStreamLine(line: string): StreamChunk | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) return null;
  const payload = trimmed.slice(5).trim();
  if (!payload) return null;
  let obj: unknown;
  try {
    obj = JSON.parse(payload);
  } catch {
    return null;
  }
  if (typeof obj !== "object" || obj === null) return null;
  const o = obj as Record<string, unknown>;
  if (typeof o.t === "string") return { kind: "token", token: o.t };
  if (typeof o.error === "string") return { kind: "error", error: o.error };
  if (o.done === true) return { kind: "done" };
  return null;
}
