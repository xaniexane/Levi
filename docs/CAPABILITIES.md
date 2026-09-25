# LEVI Capability Atlas — the honesty file

`core/levi/knowledge/capabilities/atlas.json` is the structured answer to
"what can you do?". Fourteen domains (curriculum Q&A, current events, math,
code, writing, summarization, planning, tool use & delegation, memory,
file/shell, web research, data analysis, creative work, scheduling), each
with:

- **id / name / description** — what the domain covers
- **example_prompts** — things a user can actually ask
- **tools** — the real agent tool names that serve it (asserted in tests
  against `build_default_registry()` — a domain can never claim a tool
  that doesn't exist)
- **known_limits** — what it can't do, stated plainly

## The honesty rule

The `capabilities` agent tool (and `levi capabilities [domain]`) read this
file instead of improvising. If a user asks for something outside the atlas
or the tool list, the agent says so — it does not invent abilities.

This is a deliberate inversion of the usual failure mode: instead of the
model guessing its capabilities from training vibes, the capabilities are
**data**, versioned in the repo, tested against the real registry.

## Maintenance

When a tool is added or removed, update `atlas.json` and run
`tests/test_capabilities.py` — the tool-name assertion will catch drift.
