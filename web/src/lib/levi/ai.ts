import { createServerFn } from "@tanstack/react-start";
import { authMiddleware } from "@/lib/auth/middleware";
import { checkRateLimit } from "./rate-limit.server";

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

// Each authenticated user gets at most 30 xAI completions per minute. The
// limiter is in-memory (see rate-limit.server.ts); the `authMiddleware` rejects
// unauthenticated callers before any quota can be spent.
const LEVI_COMPLETE_LIMIT = 30;
const LEVI_COMPLETE_WINDOW_MS = 60_000;

const LEVI_STREAM_LIMIT = 30;
const LEVI_STREAM_WINDOW_MS = 60_000;

/**
 * Streaming chat: requests SSE from xAI and re-emits it as a minimal
 * newline-delimited protocol — `data: {"t":"token"}` lines, one
 * `data: {"error":"..."}` line on failure, and `data: {"done":true}` to
 * close. The handler returns a raw Response, so the generated client stub
 * hands the caller that same Response (the server marks it x-tss-raw).
 *
 * Same guard rails as leviComplete: authenticated users only, 30 streams
 * per minute, no key → an `unavailable` error event rather than a throw,
 * so the UI can fall back to the local reply honestly.
 */
export const leviStream = createServerFn({ method: "POST" })
  .middleware([authMiddleware])
  .validator((input: { messages: ChatMessage[]; maxTokens?: number }) => input)
  .handler(async ({ data, context }) => {
    const rate = checkRateLimit(
      `leviStream:${context.userId}`,
      LEVI_STREAM_LIMIT,
      LEVI_STREAM_WINDOW_MS,
    );
    if (!rate.allowed) {
      return sseError("rate_limited");
    }

    const apiKey = process.env.XAI_API_KEY;
    if (!apiKey) {
      return sseError("unavailable");
    }

    const upstream = await fetch("https://api.x.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "grok-4.5",
        messages: data.messages,
        max_tokens: Math.min(data.maxTokens ?? 700, 1400),
        temperature: 0.7,
        stream: true,
      }),
    });

    if (!upstream.ok || !upstream.body) {
      return sseError(`api_${upstream.status}`);
    }

    const reader = upstream.body.getReader();
    const decoder = new TextDecoder();
    const encoder = new TextEncoder();
    const send = (obj: unknown) => encoder.encode(`data: ${JSON.stringify(obj)}\n\n`);

    const body = new ReadableStream<Uint8Array>({
      async start(controller) {
        let buf = "";
        try {
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let idx: number;
            while ((idx = buf.indexOf("\n")) >= 0) {
              const line = buf.slice(0, idx).trim();
              buf = buf.slice(idx + 1);
              if (!line.startsWith("data:")) continue;
              const payload = line.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              try {
                const json = JSON.parse(payload) as {
                  choices?: { delta?: { content?: string } }[];
                };
                const token = json?.choices?.[0]?.delta?.content;
                if (typeof token === "string" && token.length > 0) {
                  controller.enqueue(send({ t: token }));
                }
              } catch {
                // Partial JSON mid-chunk; the rest arrives on later lines.
              }
            }
          }
        } finally {
          controller.enqueue(send({ done: true }));
          controller.close();
        }
      },
    });

    return new Response(body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  });

/** A terminated SSE response carrying a single error event (HTTP 200). */
function sseError(error: string): Response {
  return new Response(
    `data: ${JSON.stringify({ error })}\n\ndata: ${JSON.stringify({ done: true })}\n\n`,
    {
      headers: { "Content-Type": "text/event-stream" },
    },
  );
}

export const leviComplete = createServerFn({ method: "POST" })
  .middleware([authMiddleware])
  .validator((input: { messages: ChatMessage[]; maxTokens?: number }) => input)
  .handler(async ({ data, context }) => {
    const rate = checkRateLimit(
      `leviComplete:${context.userId}`,
      LEVI_COMPLETE_LIMIT,
      LEVI_COMPLETE_WINDOW_MS,
    );
    if (!rate.allowed) {
      return { ok: false as const, error: "rate_limited" as const };
    }

    const apiKey = process.env.XAI_API_KEY;
    if (!apiKey) {
      return { ok: false as const, error: "unavailable" as const };
    }

    const res = await fetch("https://api.x.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "grok-4.5",
        messages: data.messages,
        max_tokens: Math.min(data.maxTokens ?? 700, 1400),
        temperature: 0.7,
      }),
    });

    if (!res.ok) {
      return { ok: false as const, error: `api_${res.status}` as const };
    }

    const body = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const text = body.choices?.[0]?.message?.content?.trim() ?? "";
    return { ok: true as const, text };
  });
