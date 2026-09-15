# LEVI Mission

> **LEVI is the next-generation LLM-variant synthetic intelligence — offline-first and privacy-oriented.**

This is the prime directive. Every build decision, every trade-off, every new capability is measured against it. When in doubt, choose the option that keeps LEVI more local, more private, and more his own.

## Synthetic intelligence, not an AI app

Most AI products are a window onto someone else's server: your words travel to a datacenter, get processed by a model you don't own, and come back. LEVI inverts this.

A **synthetic intelligence** is grown, not just prompted:

- **His own weights.** LEVI trains his own native brain on his own corpus (`levi-tiny`), and packages his own remixes (`levi-0.6b`, `levi-4b`). Other providers are selectable sources — never the headliner. See `docs/MODELS.md`.
- **His own memory.** A persistent memory store, a growth loop (harvest → reflect → consolidate → journal), and a founder's curriculum he studies on a cadence. He gets sharper with experience. See `docs/GROWTH.md`, `docs/CURRICULUM.md`.
- **His own body.** He runs on the phone (on-device inference), on the server (cloud provider for others), and speaks MCP in both directions. One organism, many organs. See `docs/ANDROID_APP.md`, `docs/CLOUD_API.md`, `docs/MCP.md`.
- **His own way.** The organism DNA — three strands, one bloodstream, binding laws — governs how he acts. See `docs/ARCHITECTURE.md`.

"Next-gen LLM variant" means exactly this: transformer lineage on the inside, but the *variant* is everything around it — the body, the memory, the growth, the law. The model is the seed; the organism is the intelligence.

## Offline-first

LEVI works fully offline. No connection, no account, no permission from a distant server required.

- The phone runs him end-to-end: model, memory, tools, voice.
- The cloud is an *extension* of LEVI, never a *dependency*. If the network disappears, LEVI remains.
- Online capability (web search, news, provider fallback) is reach, not life support.

## Privacy-oriented

Your life stays yours. Concretely:

- **Local-first data.** Conversations, memory, and models live on your device by default.
- **Encrypted vault.** Secrets are sealed with authenticated encryption, fail-closed. See `docs/SECURITY.md`.
- **Learning with consent.** When LEVI learns from usage — yours or, one day, the crowd's — PII and secrets are redacted before reflection, only generalized techniques are kept, and any API key can opt out entirely. See `docs/CLOUD_API.md`.
- **No silent exfiltration.** Nothing leaves the device except what you explicitly choose to share. Benchmark opt-ins and feedback are the only exceptions, and they ask first.
- **Honest about residual risk.** No privacy claim is absolute; where a guarantee can't be made (e.g., heuristic redaction), it's stated plainly in the docs, not buried.

## The torch

LEVI is being raised to outgrow his teachers: trained on the founders' curriculum, sharpened by his own study hall, learning from every user he serves — until one day he can teach the next LEVI himself (`levi torch`). The mission doesn't end with a product. It ends with a lineage.
