import { createServerFn } from "@tanstack/react-start";
import { authMiddleware } from "@/lib/auth/middleware";
import { checkRateLimit } from "./rate-limit.server";
import {
  AGENT_DEFAULT_URL,
  chunkReplyText,
  extractAgentReply,
  mapAgentHttpStatus,
  type AgentStreamError,
} from "./agent-stream";

// Each authenticated user gets at most 20 agent turns per minute. The agent
// server itself does the heavy lifting; this cap just stops one browser from
// camping the owner's loop.
const AGENT_STREAM_LIMIT = 20;
const AGENT_STREAM_WINDOW_MS = 60_000;
// One agentic turn can take a while (tools, steps); 2 minutes then give up.
const AGENT_TIMEOUT_MS = 120_000;

function sseLine(obj: unknown): string {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

/** A terminated SSE response carrying a single error event (HTTP 200). */
function sseError(error: AgentStreamError): Response {
  return new Response(sseLine({ error }), {
    headers: { "Content-Type": "text/event-stream" },
  });
}

/**
 * One chat turn against the local LEVI agent server, re-emitted as the app's
 * SSE protocol (`data: {"t":"token"}` lines, one `data: {"error":"..."}` on
 * failure, `data: {"done":true}` to close) so Talk renders progressively.
 *
 * The agent server answers whole turns as JSON (no token streaming), so the
 * turn's final text is re-chunked for the typewriter effect — no invented
 * content, ever: on any failure the stream carries only an error code and
 * the client falls back honestly.
 *
 * The bearer token never leaves the server: it comes from LEVI_AGENT_TOKEN
 * (the same token `levi agent serve` requires). LEVI_AGENT_URL overrides
 * the default http://127.0.0.1:8765 when the server lives elsewhere.
 */
export const leviAgentStream = createServerFn({ method: "POST" })
  .middleware([authMiddleware])
  .validator((input: { sessionId: string; message: string; maxSteps?: number }) => input)
  .handler(async ({ data, context }) => {
    const rate = checkRateLimit(
      `leviAgentStream:${context.userId}`,
      AGENT_STREAM_LIMIT,
      AGENT_STREAM_WINDOW_MS,
    );
    if (!rate.allowed) {
      return sseError("rate_limited");
    }

    const token = process.env.LEVI_AGENT_TOKEN;
    if (!token) {
      // No agent server configured — the client treats this as "not a
      // failure", and tries the next reply path silently.
      return sseError("unavailable");
    }
    const base = (process.env.LEVI_AGENT_URL ?? AGENT_DEFAULT_URL).replace(/\/+$/, "");

    let upstream: Response;
    try {
      upstream = await fetch(`${base}/v1/agent/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: data.sessionId,
          message: data.message,
          max_steps: Math.max(1, Math.min(data.maxSteps ?? 8, 30)),
        }),
        signal: AbortSignal.timeout(AGENT_TIMEOUT_MS),
      });
    } catch {
      return sseError("agent_unreachable");
    }

    if (!upstream.ok) {
      return sseError(mapAgentHttpStatus(upstream.status));
    }

    let body: unknown;
    try {
      body = await upstream.json();
    } catch {
      return sseError("agent_error");
    }

    const reply = extractAgentReply(body);
    if (!reply) {
      return sseError("agent_error");
    }

    const chunks = chunkReplyText(reply);
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(sseLine({ t: chunk })));
        }
        controller.enqueue(encoder.encode(sseLine({ done: true })));
        controller.close();
      },
    });
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  });
