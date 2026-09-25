/**
 * LEVI agent-server chat — pure helpers.
 *
 * The agent server (`levi agent serve`, POST /v1/agent/chat, bearer auth)
 * answers a whole turn as one JSON body; it does not emit tokens. The
 * server function in agent-chat.ts re-emits the turn's final text through
 * the app's shared SSE protocol (stream-protocol.ts) so Talk can render it
 * progressively. Everything here is pure (storage injectable) and
 * unit-tested in agent-stream.unit.test.ts.
 */

/** Base URL of the agent server; override with LEVI_AGENT_URL server-side. */
export const AGENT_DEFAULT_URL = "http://127.0.0.1:8765";

export type AgentStreamError =
  | "unavailable" // no LEVI_AGENT_TOKEN configured server-side
  | "rate_limited" // per-user stream budget spent
  | "agent_unreachable" // fetch threw or timed out
  | "agent_unauthorized" // 401/403 from the agent server
  | "agent_bad_request" // 400 — e.g. missing session_id/message
  | "agent_error"; // any other failure, incl. ok:false without usable text

/** Map an HTTP status from the agent server to a stable error code. */
export function mapAgentHttpStatus(status: number): AgentStreamError {
  if (status === 401 || status === 403) return "agent_unauthorized";
  if (status === 400) return "agent_bad_request";
  return "agent_error";
}

/**
 * Pull the assistant's final text out of a /v1/agent/chat JSON body.
 * Returns null when the turn failed or carried no usable text — the caller
 * must fall back honestly, never invent a reply.
 */
export function extractAgentReply(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const transcript = (body as { transcript?: unknown }).transcript;
  if (typeof transcript !== "object" || transcript === null) return null;
  const t = transcript as { ok?: unknown; final?: unknown };
  if (t.ok === false) return null;
  return typeof t.final === "string" && t.final.trim() ? t.final : null;
}

/**
 * Split a completed reply into progressive chunks — sentences first, word
 * groups for long sentences — so the UI can render it as a stream. The
 * concatenation of the chunks is the original text, byte for byte.
 */
export function chunkReplyText(text: string, maxChunk = 64): string[] {
  const chunks: string[] = [];
  // Split on sentence boundaries; keep the delimiter with its sentence.
  const sentences = text.split(/(?<=[.!?…])\s+/);
  for (const sentence of sentences) {
    if (!sentence) continue;
    if (sentence.length <= maxChunk) {
      chunks.push(sentence);
      continue;
    }
    let buf = "";
    for (const word of sentence.split(/\s+/)) {
      const next = buf ? `${buf} ${word}` : word;
      if (next.length > maxChunk && buf) {
        chunks.push(buf);
        buf = word;
      } else {
        buf = next;
      }
    }
    if (buf) chunks.push(buf);
  }
  return chunks;
}

/**
 * Stable per-browser agent session id, persisted in localStorage. The agent
 * server requires session_id; one id per browser keeps server-side session
 * continuity across page reloads.
 */
const SESSION_KEY = "levi-agent-session";

function freshSessionId(): string {
  return `web-${Math.random().toString(36).slice(2, 10)}`;
}

export function getAgentSessionId(
  storage: Pick<Storage, "getItem" | "setItem"> = globalThis.localStorage,
): string {
  try {
    const existing = storage.getItem(SESSION_KEY);
    if (existing && existing.trim()) return existing;
    const id = freshSessionId();
    storage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return freshSessionId();
  }
}
