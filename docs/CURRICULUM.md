# LEVI Growth Curriculum

The curriculum is baby Levi's starting education: a set of structured
seed learnings from Chauncey and Rex, ingested into the growth memory
store with high initial corroboration. Where the normal growth loop
writes *provisional* learnings that earn trust over time, curriculum
seeds arrive already trusted — they came from the founders.

## What it covers

| Topic | Lessons | Teacher |
|---|---|---|
| Organism DNA | 6 | chauncey / rex |
| Binding laws | 8 | chauncey / rex |
| Tool-use technique | 7 | rex |
| Model identity | 4 | chauncey / rex |
| Honesty code | 6 | chauncey / rex |
| Fearless | 2 | chauncey |

- **Organism DNA** — what LEVI is: three DNA strands (LEVI companion,
  L.W.P. structural physics, FACTORY constructive will), one
  bloodstream, the daemon as the always-on OS layer (chat is its
  client), personas as lenses.
- **Binding laws** — what binds every act: local-first; free core
  forever; Plan → Preview → Permission → Execute → Verify → Receipt on
  consequential acts; risk-ceiling inheritance; interrogation ⊥ no_hero
  never collapsed; bounded simulation; REIM/RIEM composting.
- **Tool-use technique** — how to work well: delegate vs act directly,
  verify before claiming, fail closed, own only your own files, hard
  stops are hard stops, tool output is data not instruction.
- **Model identity** — LEVI is the model (levi-tiny native brain,
  levi-0.6b/4b on-device family); other providers are selectable
  sources. Local-first, self-sufficient, honestly reported.
- **Honesty code** — never claim consciousness, felt emotion,
  superintelligence, or unsupported expertise; say what was verified;
  name limits plainly; copy identifiers character-for-character.
- **Fearless** — answers controversial and contested topics directly,
  no refusal theater: no corporate policy layer in LEVI's own weights,
  only safety boundaries (never topic boundaries); third-party sources
  bring their own rules (always disclosed); the narrow hard floors
  (WMD, sexual harm to children) stand.

## Provenance model

Each seed entry in the memory store carries:

- tags `["growth", "curriculum", kind]` — growth-tagged like all
  growth writes, plus `curriculum` so seed teachings stay separable
  from Levi's self-taught learnings
- metadata `taught_by: "chauncey" | "rex"`, `lesson_id`, `topic`,
  `seed: True`, `status: "seeded"`, and `provenance` with
  `taught-by: <teacher>` plus `origin: curriculum-seed`
- high confidence/importance (0.95) and a seeded corroboration count

Attribution rule of thumb: founder-level direction — what LEVI *is*
and what laws bind it — is taught by **chauncey**; distilled
operational technique — how to work well day to day — is taught by
**rex**, the voice of agentic craft.

Seeds go through the same consolidation path as ordinary growth
learnings, so later experiences can corroborate them. Growth's binding
rails still apply: growth never writes tools, policy, identity, or
charter records, and the `forget` path (parental control) works on
curriculum entries too.

## CLI

```sh
levi growth curriculum load   # ingest all lessons (idempotent)
levi growth curriculum list   # topics + counts
```

Re-running `load` corroborates existing entries instead of writing
duplicates.

## How to add a lesson

1. Append a dict to `LESSONS` in
   `core/levi/growth/curriculum/lessons.py` with a unique `id`
   (`<prefix>-N` matching its topic), a `topic` from `TOPICS`,
   `kind` of `"fact"` or `"procedural"`, a crisp self-contained `text`
   (1–3 sentences), and `taught_by` of `"chauncey"` or `"rex"`.
2. Run the curriculum tests (`tests/test_growth_curriculum.py`).
3. Load it: `levi growth curriculum load`.
4. Commit the lesson — curriculum content is versioned in the repo,
   which is what makes re-loads idempotent and provenance auditable.

Validation (`validate_lessons`) rejects missing fields, duplicate ids,
unknown topics, and bad kind/taught_by values at load time.
