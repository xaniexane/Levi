# Sidewinder seeds — authoring guide

## topics.jsonl — the intake queue

One JSON object per line, full course schema (see `../schema.py`):

```json
{"id": "sw-plumbing-014", "title": "Replace a faucet cartridge", "domain": "plumbing",
 "tracks": ["restore"], "level": "applied", "prerequisites": ["sw-foundations-007"],
 "difficulty": 2,
 "mechanism_check": ["..."], "improvised_tools": ["..."],
 "steps": ["..."], "stop_conditions": ["..."]}
```

Rules:
- `id`: `sw-<domain>-NNN`, next free number in the domain shard.
- `tracks`: >= 1 of build/create/improve/restore/combine/improvise.
- `level`: foundation (no prereqs) | applied | mastery.
- `prerequisites`: entry ids that must come first in the learning path.
- Keep every section terse (<= 400 chars per item). No filler.
- Crisis domain: first stop condition MUST call for professional help
  first; include an explicit "do not attempt if..." condition.

Run `levi sidewinder grow --dry-run` to validate, then
`levi sidewinder grow` to promote into the corpus.

## planned_titles.txt — the roadmap

`track | domain | title` lines. Add titles freely — this is the plan that
scales to thousands. `levi sidewinder stubs <n>` turns the next unbuilt
titles into blank writer stubs in `stubs.jsonl`.

## stubs.jsonl — writer scaffolding

Unfilled stubs. Never promoted as-is (`grow` ignores this file; the
schema rejects stubs). Fill the FILL sections, move finished lines into
`topics.jsonl`, then grow.
