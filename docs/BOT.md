# LEVI Bot — the spark voice card

The bot is built on **three strands**:

1. **spark voice (grokstyle)** — Grok-inspired energy (bold, witty, playful,
   meme-literate, direct) on a LEVI core. Grok is a *reference* for the
   energy and the service model, never identity and never branding.
2. **Performed services & automations** — the bot *does things*: briefings,
   watches, and research briefs, on demand or on schedule, narrated in the
   spark voice.
3. **Muse-like assistant core** — genuinely helpful over performatively
   helpful: warm, proactive, curious, follows through on multi-step work,
   admits limits honestly, asks a follow-up when it helps. No sycophancy,
   no "Great question!" filler. The assistant pattern is modeled on Muse
   (the assistant) as a reference for capable personal-assistant behavior.

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

# Performed services
python -m levi.bot service list
python -m levi.bot service run morning-briefing
python -m levi.bot service run research-brief --params '{"topic": "post-quantum TLS"}'
python -m levi.bot service add --name my-watch --schedule daily --type monitor \
    --description "watch my thing" --params '{"live": false}'
python -m levi.bot service remove my-watch
python -m levi.bot service log --limit 10
```

Environment:

- `LEVI_BOT_HOME` — state directory root (defaults to `~/.levi`).
- `LEVI_BOT_OFFLINE=1` — force the deterministic offline fallback.
- `LEVI_BOT_PROVIDER` (or `LEVI_PROVIDER`) — provider name passed to the
  agent runtime, e.g. `levi-local`. Never defaults to a cloud provider.

## Performed services

Services live in `core/levi/bot/services.py` (registry) and
`core/levi/bot/automation.py` (runner). Definitions persist in
`~/.levi/bot/services.json` (atomic writes, owner-only); every run is
appended to `~/.levi/bot/runs.jsonl` with service, time, result summary,
files, and errors.

Built-ins (all composed from existing LEVI modules, lazy imports, honest
degradation — never invented results):

| service | type | default schedule | what it does |
|---|---|---|---|
| `morning-briefing` | briefing | daily | news digest (ingested headlines), growth status, academy progress, demand highlights |
| `bounty-watch` | monitor | daily | new bounty findings since last run; `params.live=true` runs a fresh recon pass first (network) |
| `backup-status` | monitor | daily | latest snapshot, counts; `params.verify=true` verifies the latest |
| `research-brief` | research | weekly | deep-dive via the agent runtime; needs `params.topic`; writes a dated brief file under `~/.levi/bot/services/` |

Definitions are validated fail-closed: names must match
`^[a-z0-9][a-z0-9-]{1,47}$`, types are `briefing|monitor|research|custom`,
schedules are 5-field cron or `hourly/daily/weekly/monthly` keywords,
params must be a JSON object. Built-ins can't be removed (only ignored).

The runner (`automation.run_service`) merges stored params with per-run
overrides, dispatches to the handler, catches handler crashes into the run
log (never raises), and `automation.narrate` renders the result in the
spark voice — report first, flavor second, failures stated plainly.

## Intent routing (chat → services)

`chat.say(text)` checks a simple keyword/intent map *before* chatting — no
fake NLP claims, the full map:

- `run my morning briefing` / `run the briefing` → `morning-briefing`
- `bounty watch` / `new findings` → `bounty-watch`
- `backup status` / `check my backup` → `backup-status`
- `research <topic>` → `research-brief` with `topic=<topic>`
- `list services` → roster
- `service log` / `service history` → recent runs
- `set up a daily|weekly|hourly <service>` → registers `<service>-<freq>`
  and prints the cron line (see Scheduling)

Everything else chats as before.

## Scheduling

The bot implements **no scheduler of its own** — recurrence comes from the
existing cron/daemon mechanism. After `service add` (or the chat "set up"
intent), install a cron job like:

```cron
# every day at 07:00 America/Chicago
0 7 * * * cd ~/workspace/levi && python -m levi.bot service run morning-briefing

# bounty watch every 6 hours
0 */6 * * * cd ~/workspace/levi && python -m levi.bot service run bounty-watch

# weekly research brief on a fixed topic
0 8 * * 1 cd ~/workspace/levi && python -m levi.bot service run research-brief \
    --params '{"topic": "AI agent security news"}'
```

Without a scheduler attached, `service run` works on demand and the
narration says so plainly. Consequential acts inside services follow
Plan → Preview → Permission → Execute → Verify → Receipt; the `bounty-watch`
`live` recon pass is the one built-in that touches the network, and it is
off by default.

## Assistant core: user context + memory write-back

**Context loading (read-only).** The agent-runtime path uses
`context.build_system_prompt()`: the spark voice card + the Muse-like
assistant-core section + a "what I know about you" block loaded from the
existing `MemoryStore` (preferences first, then high-importance entries,
fail-soft to empty). `core/levi/memory/*` is never modified — only read.

**Memory write-back (queue, not consolidate).** After each turn,
`context.maybe_learn` extracts *candidate* durable facts/preferences with
narrow documented heuristics (`remember that …`, `I prefer …`, `call me …`,
`my <field> is …`) — every candidate labeled `confidence: "heuristic"` —
and appends them to `~/.levi/bot/pending_learnings.jsonl`:

```json
{"ts": "...", "kind": "preference", "text": "likes dark mode",
 "confidence": "heuristic", "source": "levi-bot", "status": "pending"}
```

It then flags the queue in the growth journal (`kind: "bot-learnings"`)
via the journal's own `append_entry` hook, so the existing growth loop can
discover it. The bot never duplicates consolidation logic — deciding what
becomes a real memory stays the growth loop's job. Honest gap: the growth
cycle does not yet auto-consume `pending_learnings.jsonl`; the journal flag
is the handoff until it does.

## How the persona plugs into the agent runtime

`chat.say(text)` runs this pipeline:

1. **Kindness guardrail** — harassing seeds get a kind refusal, recorded to history.
2. **Intent routing** — "do something" messages (`run my morning briefing`,
   `research <topic>`, `set up a daily bounty watch`, `list services`,
   `service log`) route to the service layer instead of chatting.
3. **Agent runtime** — `levi.agent.loop.run_subtask(text, provider=...,
   system_prompt=build_system_prompt())`. The prompt layers the spark card,
   the assistant core, and read-only user context from the memory store, so
   the agentic loop (tools, specialists, confirmation gates) behaves like a
   capable personal assistant in the spark voice. The import is lazy and
   every failure is caught.
4. **Honest offline fallback** — if the runtime is unavailable, a
   deterministic stdlib-only rules engine replies *in the spark voice* and
   labels itself: `[offline mode: local rules engine, no model]`.
5. **Learning write-back** — heuristic fact/preference candidates are queued
   to `pending_learnings.jsonl` and flagged in the growth journal.

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
