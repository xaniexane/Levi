import { TSS_SERVER_FUNCTION, createServerFn } from "./ssr.mjs";
import { authMiddleware } from "./middleware-DPak2s3B.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/ai-diGzfN7j.js
var createServerRpc = (serverFnMeta, splitImportFn) => {
	const url = "/_serverFn/" + serverFnMeta.id;
	return Object.assign(splitImportFn, {
		url,
		serverFnMeta,
		[TSS_SERVER_FUNCTION]: true
	});
};
var buckets = /* @__PURE__ */ new Map();
function checkRateLimit(key, limit, windowMs) {
	const now = Date.now();
	const recent = (buckets.get(key) ?? []).filter((t) => now - t < windowMs);
	if (recent.length >= limit) {
		const oldest = recent[0] ?? now;
		return {
			allowed: false,
			retryAfterMs: Math.max(0, windowMs - (now - oldest))
		};
	}
	recent.push(now);
	buckets.set(key, recent);
	if (buckets.size > 1e4) {
		for (const [k, stamps] of buckets) if (stamps.every((t) => now - t >= windowMs)) buckets.delete(k);
	}
	return { allowed: true };
}
var LEVI_COMPLETE_LIMIT = 30;
var LEVI_COMPLETE_WINDOW_MS = 6e4;
var leviComplete_createServerFn_handler = createServerRpc({
	id: "c689c598a9c5ff4161674fe4077d01d0f3537dabde2966e5bacff83a302c071c",
	name: "leviComplete",
	filename: "src/lib/levi/ai.ts"
}, (opts) => leviComplete.__executeServer(opts));
var leviComplete = createServerFn({ method: "POST" }).middleware([authMiddleware]).validator((input) => input).handler(leviComplete_createServerFn_handler, async ({ data, context }) => {
	if (!checkRateLimit(`leviComplete:${context.userId}`, LEVI_COMPLETE_LIMIT, LEVI_COMPLETE_WINDOW_MS).allowed) return {
		ok: false,
		error: "rate_limited"
	};
	const apiKey = process.env.XAI_API_KEY;
	if (!apiKey) return {
		ok: false,
		error: "unavailable"
	};
	const res = await fetch("https://api.x.ai/v1/chat/completions", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${apiKey}`
		},
		body: JSON.stringify({
			model: "grok-4.5",
			messages: data.messages,
			max_tokens: Math.min(data.maxTokens ?? 700, 1400),
			temperature: .7
		})
	});
	if (!res.ok) return {
		ok: false,
		error: `api_${res.status}`
	};
	return {
		ok: true,
		text: (await res.json()).choices?.[0]?.message?.content?.trim() ?? ""
	};
});
//#endregion
export { leviComplete_createServerFn_handler };
