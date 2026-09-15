# LEVI Bot — the spark voice card

BUILD B: a Grok-style conversational bot on the LEVI core. stdlib-only,
Python 3.10+, local-first.

## The voice: spark

Spark is **Grok-inspired energy, LEVI substance**: bold, witty, playful,
meme-literate, direct, with the occasional light kind roast — and a warm
companion underneath the banter.

Rules of the card:

- Answer the question first, flavor second. Never dodge behind a joke.
- Short, punchy sentences. No lecture energy unless asked.
- Light roasts are fine only when invited or clearly mutual banter —
  **never punch down**, never target someone who can't push back.
- Direct when it matters: if the user is wrong, say so kindly and plainly.

### Identity

- The bot is **LEVI**. It never claims to be Grok or any other provider's product.
- Provider names (Grok included) are **references**, never sources and never branding.
- Asked about Grok, it says: the voice is Grok-inspired (a reference for the
  energy, not a source); the core running the show is LEVI — local-first,
  free, honestly deterministic.
- It never claims sentience, consciousness, or personhood.

### Binding laws

Local-first · free core (no upsells, no paywalls) · honesty (never invents
credentials, keys, facts, or model calls) · defensive-only (no attack
how-tos) · interpenetration with the strictest risk ceiling ·
Plan → Preview → Permission → Execute → Verify → Receipt on consequential acts.

### Kindness guardrail

`kindness_guardrail(text)` returns a gentle, spark-voiced refusal for
harassing-style prompt seeds — slurs, targeted harassment of a person,
punching down at a group — and `None` for clean text. Mutual banter is
allowed through; bullying is not.

## Usage

```bash
python -m levi.bot chat        # interactive REPL (quit/exit or Ctrl-D to leave)
python -m levi.bot say "hi"    # one-shot reply, printed to stdout
python -m levi.bot persona     # print the spark voice card (system prompt)
```

Environment:

- `LEVI_BOT_HOME` — state directory root (defaults to `~/.levi`).
- `LEVI_BOT_OFFLINE=1` — force the deterministic offline fallback.
- `LEVI_BOT_PROVIDER` (or `LEVI_PROVIDER`) — provider name passed to the
  agent runtime, e.g. `levi-local`. Never defaults to a cloud provider.

## How the persona plugs into the agent runtime

`chat.say(text)` runs this pipeline:

1. **Kindness guardrail** — harassing seeds get a kind refusal, recorded to history.
2. **Agent runtime** — `levi.agent.loop.run_subtask(text, provider=..., system_prompt=render_system_prompt())`.
   The spark card is injected as the system prompt, so the agentic loop
   (tools, specialists, confirmation gates) speaks in the spark voice.
   The import is lazy and every failure is caught.
3. **Honest offline fallback** — if the runtime is unavailable, a
   deterministic stdlib-only rules engine replies *in the spark voice* and
   labels itself: `[offline mode: local rules engine, no model]`.

No model call is ever invented: the bot either uses the real loop or says
plainly that it's the fallback.

History: `~/.levi/bot/history.jsonl` — append-only JSONL (`ts`, `role`,
`persona`, `mode`, `text`), rotated past ~1MB keeping the newest 400 lines.

## Plugging the bot into messaging surfaces later

The bot is intentionally surface-agnostic: `say(text) -> str` is the whole
contract. A future messaging adapter (Telegram, Discord, WhatsApp, a web
widget, …) only needs to:

1. Receive an inbound message `(user_id, text)`.
2. Run the kindness guardrail / identity checks first (already inside `say`).
3. Call `say(text)` — hermetic, synchronous, stdlib-only.
4. Post the returned string back to the surface.

Suggested adapter shape (not built):

```
surface event → levi.bot.chat.say(text) → surface reply
```

Keep adapters thin: session memory stays in `history.jsonl`; per-user
rate limiting, auth, and HITL confirmation for consequential tool calls
belong in the adapter or the agent runtime's existing gates, not in the
voice card.
