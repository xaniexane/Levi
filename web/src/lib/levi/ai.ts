import { createServerFn } from "@tanstack/react-start";

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

export const leviComplete = createServerFn({ method: "POST" })
  .validator((input: { messages: ChatMessage[]; maxTokens?: number }) => input)
  .handler(async ({ data }) => {
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
