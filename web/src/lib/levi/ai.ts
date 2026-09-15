import { createServerFn } from "@tanstack/react-start";
import { authMiddleware } from "@/lib/auth/middleware";
import { checkRateLimit } from "./rate-limit.server";

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

// Each authenticated user gets at most 30 xAI completions per minute. The
// limiter is in-memory (see rate-limit.server.ts); the `authMiddleware` rejects
// unauthenticated callers before any quota can be spent.
const LEVI_COMPLETE_LIMIT = 30;
const LEVI_COMPLETE_WINDOW_MS = 60_000;

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
