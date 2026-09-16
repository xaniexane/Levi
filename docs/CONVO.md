# thread-sense — conversational proprioception

Most chatbots remember the last N turns. LEVI feels the *shape* of the
conversation. thread-sense is conversational proprioception: the organism
sensing its own dialogue body.

## The concept

A conversation is not a list of turns — it is a living structure:

- **Threads** are topics with *salience*: they ignite when mentioned, decay
  when ignored, and **reignite on callback**. "Back to the server thing"
  should work — and now it does.
- **Entities** are things named, with lightweight coreference. "Restart it"
  resolves to the most salient compatible entity.
- **Open loops** are what the organism *owes*: questions it asked the user,
  promises it made ("I'll check that"). They stay visible until closed.
- **Session facts** are claims established — the substrate of the immune sense.
- **Semantic recall** answers "which *earlier* turns matter to *this* one?"
  with the hybrid ranker, not recency. Turn 184 can beat turn 199.

## Components

| module | role |
|---|---|
| `state.py` | `DialogueState` — threads, entities, loops, facts; per-turn `update()` |
| `recall.py` | `recall_turns()` — hybrid retrieval over the conversation's own history |
| `guard.py` | `check_contradictions()` — the immune sense; flags, never censors |
| `render.py` | `render_block()` (prompt block) + `render_constellation()` (the starfield) |
| `__main__.py` | `python -m levi.convo demo` / `state <session.jsonl>` |

All extraction is stdlib heuristics, **precision over recall**: thread-sense
would rather miss a subtle link than hallucinate one. Everything is
deterministic.

### The constellation

`render_constellation()` draws the conversation as a starfield using
`levi.ux`: threads are stars whose brightness is live salience
(`meter`), with sparkline trails showing each thread's life across turns,
entities as satellites, open loops as pending orbits. Run the demo and watch
a thread die and reignite.

## Wiring (additive)

`agent/chat.py` and `agent/loop.py` are owned by another worker's pass —
**do not edit them yet**. The pending patch, to apply after that pass lands:

```python
# agent/chat.py — in the per-turn handler, after appending the turn:
from levi.convo.state import DialogueState          # PENDING
from levi.convo.render import render_block           # PENDING
from levi.convo.recall import recall_turns           # PENDING
from levi.convo.guard import check_contradictions    # PENDING

state = DialogueState()                              # PENDING (session-scoped)

changed = state.update(speaker, text)                # PENDING (every turn)
recalled = recall_turns(text, state.turns)          # PENDING
prompt_prefix = render_block(state, recalled)        # PENDING (prepend to prompt)
findings = check_contradictions(reply, state.facts)  # PENDING (on LEVI replies)
```

```python
# agent/loop.py — inside run_subtask, before building the prompt:
from levi.convo.render import render_block           # PENDING
# if a DialogueState is passed in, prepend render_block(state) to system  # PENDING
```

Findings from the guard are advisory: surface a gentle "earlier you said…",
log them, or ignore — never silently rewrite the reply.

## Honest limits

- Coreference is heuristic (most salient recent entity). It misses subtle
  cases rather than inventing links; "it" with two equally live candidates
  picks the brighter star and says so.
- The contradiction sense catches direct negations and attribute conflicts,
  not paraphrased disagreements or temporal change ("it was X, now it's Y"
  will flag — the caller must allow legitimate updates).
- Thread matching is keyword-Jaccard; heavy paraphrase across turns may
  start a new thread instead of joining.
- Recall quality rides on `levi.memory.retrieval`; tiny histories fall back
  to keyword overlap with a labeled note.
- The demo's final contradiction is deliberate — a probe, not a bug.
