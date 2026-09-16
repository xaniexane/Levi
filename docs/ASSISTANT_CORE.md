# LEVI Assistant Core

The Muse-like behavioral core for the whole agent runtime — promoted out of
the spark-bot prototype (`levi.bot.persona` / `levi.bot.context`) so that
**every** LEVI surface behaves like a genuinely capable personal assistant:
`agent run`, `agent chat`, served requests — not just the bot.

Implemented in `core/levi/agent/assistant.py` (stdlib-only, no side
effects). The runtime adopts it via the pending patch below.

## The principle

Three behaviors, everywhere:

1. **Helpful** — genuinely helpful over performatively helpful. No
   "Great question!" filler, no throat-clearing. Proactive: offer the next
   useful step instead of waiting to be asked twice. Curious: one good
   follow-up when it would genuinely help; never interrogate. Follow
   through on multi-step work and report back compactly.
2. **Remembers** — carries what it knows about the user (preferences,
   facts, relationships) into every run from the memory store, and proposes
   new learnings from conversation for the growth loop to consolidate.
3. **Honest** — states limits plainly, never invents facts or tool results,
   no sycophancy (agrees only when true; pushes back kindly when the user
   is wrong).

## Muse as reference (not identity)

Consistent with the repo's references rule: providers are references,
never identity. The assistant *pattern* — a capable, warm, proactive
personal assistant — is modeled on Muse (the assistant) as a reference
for behavior. LEVI never claims to be Muse, Grok, or any other provider's
product. The prompt says this explicitly; `tests/test_assistant_core.py`
scans for identity claims.

## What `assistant.py` provides

- `assistant_system_prompt(identity="LEVI")` — the composable prompt
  section. Voice layers (spark, etc.) layer on top; they never replace it.
- `load_user_context(store=None)` — read-only "what I know about you"
  block: preferences first, then facts, then relationships, capped lines,
  fail-soft to `""`. Never crashes the caller.
- `candidate_learnings(transcript_text)` — narrow, documented heuristics
  ("remember that…", "I prefer…", "call me…", corrections) producing
  `{content, kind, confidence: "heuristic", source: "assistant-core"}`
  proposals. It *proposes*; consolidation stays the growth loop's job.
- `build_agent_prompt(user_text, store=None)` — core + user context,
  ready to prepend to any agent run.

## Pending integration patch (DO NOT APPLY YET)

The other worker's hardening pass owns `core/levi/agent/loop.py`,
`chat.py`, and `server.py`. Apply these exact, minimal hookups **after**
that pass lands. Each is a 3-line change.

### 1. `core/levi/agent/loop.py` — `run_subtask`

Inside `run_subtask`, just before the `system = _build_system_prompt(...)`
line (~line 256):

```python
# --- PENDING: assistant core (apply after hardening pass lands) ---
from levi.agent.assistant import build_agent_prompt
if system_prompt is None:
    system_prompt = build_agent_prompt(task)
# --- end PENDING ---
```

Explicit caller overrides (like the bot's spark prompt) are untouched —
the core fills in only when no override is given.

### 2. `core/levi/agent/chat.py` — `ConversationManager.__init__`

Where `self.system_prompt = system_prompt` is set (~line 252):

```python
# --- PENDING: assistant core (apply after hardening pass lands) ---
from levi.agent.assistant import build_agent_prompt
self.system_prompt = system_prompt or build_agent_prompt("")
# --- end PENDING ---
```

And after each user turn is recorded, queue learning proposals for the
growth loop (mirroring `levi.bot.context.queue_learnings`):

```python
# --- PENDING: assistant core (apply after hardening pass lands) ---
from levi.agent.assistant import candidate_learnings
for cand in candidate_learnings(user_text):
    append_pending_learning(cand)  # shared queue writer; adopt from bot
# --- end PENDING ---
```

### 3. `core/levi/agent/server.py` — the `run_subtask` call site

At the `run_subtask(...)` call in the run handler (~line 349):

```python
# --- PENDING: assistant core (apply after hardening pass lands) ---
from levi.agent.assistant import build_agent_prompt
transcript = run_subtask(
    task,
    ...
    system_prompt=build_agent_prompt(task),
)
# --- end PENDING ---
```

(`_run_kwargs` does not accept a caller system prompt today, so the
server always builds one from the core.)

## Limits (honest)

- `load_user_context` reads only the local `MemoryStore`; it does not do
  semantic retrieval — pair with the RAG/hybrid retrieval work when that
  lands if recall needs to be smarter.
- `candidate_learnings` is regex heuristics, labeled as such. Precision
  over recall: it will miss subtle learnings rather than hallucinate them.
- The core changes *tone and behavior*, not capabilities. Tool access,
  permissions, and safety gates are unchanged.
