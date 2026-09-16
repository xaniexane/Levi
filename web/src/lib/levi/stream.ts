import { leviStream, type ChatMessage } from "./ai";
import { leviAgentStream } from "./agent-chat";
import { getAgentSessionId } from "./agent-stream";
import { parseStreamLine } from "./stream-protocol";

export type StreamChatOptions = {
  messages: ChatMessage[];
  maxTokens?: number;
  signal?: AbortSignal;
  /** Called for every token as it arrives. */
  onToken: (token: string) => void;
};

export type StreamAgentChatOptions = {
  message: string;
  maxSteps?: number;
  signal?: AbortSignal;
  /** Called for every token as it arrives. */
  onToken: (token: string) => void;
};

/**
 * Consume the app's SSE protocol (`data: {"t":"token"}` … `data: {"done"}`)
 * from a server-function Response, feeding tokens to onToken as they arrive.
 * Resolves with the full text, or with an error so the caller can fall back
 * to the next reply path honestly.
 */
async function consumeSse(
  res: Response,
  onToken: (token: string) => void,
): Promise<{ text: string; error?: string }> {
  if (!res.ok || !res.body) {
    return { text: "", error: `http_${res.status}` };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  let buf = "";

  const handleLine = (line: string): string | null => {
    const chunk = parseStreamLine(line);
    if (!chunk) return null;
    if (chunk.kind === "token") {
      text += chunk.token;
      onToken(chunk.token);
      return null;
    }
    if (chunk.kind === "error") return chunk.error;
    return "done";
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx);
      buf = buf.slice(idx + 1);
      const terminal = handleLine(line);
      if (terminal === "done") return { text };
      if (terminal) return { text, error: terminal };
    }
  }
  // Trailing fragment without a newline.
  if (buf.trim()) {
    const terminal = handleLine(buf);
    if (terminal && terminal !== "done") return { text, error: terminal };
  }
  return { text };
}

/**
 * Open a streaming chat and feed tokens to onToken as they arrive.
 * Resolves with the full text, or with an error so the caller can fall
 * back to the local reply honestly.
 */
export async function streamChat(opts: StreamChatOptions): Promise<{
  text: string;
  error?: string;
}> {
  const res = (await leviStream({
    data: { messages: opts.messages, maxTokens: opts.maxTokens },
    signal: opts.signal,
  })) as unknown as Response;
  return consumeSse(res, opts.onToken);
}

/**
 * One turn against the local LEVI agent server (via the leviAgentStream
 * server function). Same SSE protocol as streamChat; resolves with an error
 * code when the agent server is unavailable or fails, so the caller can fall
 * back to the next reply path. "unavailable" means no agent server is
 * configured — not a failure worth announcing.
 */
export async function streamAgentChat(opts: StreamAgentChatOptions): Promise<{
  text: string;
  error?: string;
}> {
  const res = (await leviAgentStream({
    data: {
      sessionId: getAgentSessionId(),
      message: opts.message,
      maxSteps: opts.maxSteps,
    },
    signal: opts.signal,
  })) as unknown as Response;
  return consumeSse(res, opts.onToken);
}
