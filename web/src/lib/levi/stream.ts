import { leviStream, type ChatMessage } from "./ai";
import { parseStreamLine } from "./stream-protocol";

export type StreamChatOptions = {
  messages: ChatMessage[];
  maxTokens?: number;
  signal?: AbortSignal;
  /** Called for every token as it arrives. */
  onToken: (token: string) => void;
};

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
      opts.onToken(chunk.token);
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
